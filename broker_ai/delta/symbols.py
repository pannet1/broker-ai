from __future__ import annotations
import pandas as pd
from datetime import datetime
import os
import yaml
import requests

from broker_ai.symbols import Symbols, ExchangeLiteral, OptionsLiteral, Symbol as SymbolType, DEPTH


class Symbol(Symbols):
    def __init__(self, exchange: ExchangeLiteral, symbol: str, data_path: str | None = None):
        self.exchange = exchange
        self.symbol = symbol
        self.diff: int = 0
        self.df: pd.DataFrame = pd.DataFrame()
        
        # Default data path: repo_root/data/
        if data_path is None:
            repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.data_path = os.path.join(repo_root, 'data')
        else:
            self.data_path = data_path
        
        self._load_config()
        self.load()

    def _load_config(self):
        '''Load yaml config.'''
        config_path = os.path.join(os.path.dirname(__file__), 'delta.yaml')
        try:
            with open(config_path, 'r') as f:
                self._config = yaml.safe_load(f)
            self._download_url = self._config.get('download_url', '')
            self._option_type_map = self._config.get('option_type_map', {'call_options': 'CE', 'put_options': 'PE'})
            self._expiry_format = self._config.get('expiry_format', '%d%b%Y')
        except FileNotFoundError:
            self._download_url = ''
            self._option_type_map = {'call_options': 'CE', 'put_options': 'PE'}
            self._expiry_format = '%d%b%Y'

    def download(self) -> dict:
        '''Fetch raw data from Delta Exchange API.'''
        if not self._download_url:
            raise ValueError('download_url not configured in delta.yaml')
        
        print(f'Downloading: {self._download_url}')
        response = requests.get(self._download_url)
        data = response.json()
        return data.get('result', [])

    def normalize(self, raw: list) -> pd.DataFrame:
        '''Convert raw data to standard columns.'''
        df = pd.DataFrame(raw)
        
        # Map contract_type to option_type
        df['option_type'] = df['contract_type'].map(self._option_type_map).fillna('')
        
        # Parse expiry from settlement_time
        def parse_expiry(ts):
            if not ts:
                return ''
            try:
                dt = datetime.strptime(ts[:10], '%Y-%m-%d')  # Take only date part
                return dt.strftime(self._expiry_format)
            except:
                return ''
        
        df['expiry_date'] = df['settlement_time'].apply(parse_expiry)
        
        # Map columns
        df['tradingsymbol'] = df['symbol']
        df['token'] = df['id'].astype(str)
        df['strike'] = pd.to_numeric(df['strike_price'], errors='coerce').fillna(0).astype(int)
        
        # contract_value is string like '0.001', convert to lot size
        contract_value = pd.to_numeric(df['contract_value'], errors='coerce').fillna(1)
        df['lot_size'] = (1 / contract_value).fillna(1).astype(int)
        
        df['exchange'] = self.exchange
        
        # ws_token is just the token (integer)
        df['ws_token'] = df['token']
        
        # Keep underlying for filtering
        df['underlying'] = df['underlying_asset'].apply(lambda x: x.get('symbol', '') if isinstance(x, dict) else '')
        
        # Keep only standard columns
        cols = ['exchange', 'tradingsymbol', 'token', 'expiry_date', 'strike', 
                'option_type', 'lot_size', 'ws_token', 'underlying']
        return df[cols]

    def load(self):
        '''Load from data or download and normalize.'''
        os.makedirs(self.data_path, exist_ok=True)
        data_file = os.path.join(self.data_path, f'{self.exchange}_{self.symbol}.csv')

        if os.path.exists(data_file):
            mtime = datetime.fromtimestamp(os.path.getmtime(data_file)).date()
            if mtime == datetime.today().date():
                self.df = pd.read_csv(data_file)
                self._derive_diff()
                return

        raw = self.download()
        self.df = self.normalize(raw)
        self._derive_diff()
        
        # Keep only standard columns before saving
        cols = ['exchange', 'tradingsymbol', 'token', 'expiry_date', 'strike', 
                'option_type', 'lot_size', 'ws_token', 'underlying']
        self.df[cols].to_csv(data_file, index=False)
        print(f'Cached to: {data_file}')

    def _derive_diff(self):
        '''Derive strike interval from adjacent strikes.'''
        expiry = self.find('expiry_date')
        if not expiry:
            self.diff = 100
            return
        
        df_filtered = self.df[
            (self.df['underlying'] == self.symbol) &
            (self.df['expiry_date'] == expiry) &
            (self.df['strike'] > 0)
        ].sort_values('strike')
        
        if len(df_filtered) < 2:
            self.diff = 100
            return
        
        df_filtered['diff'] = df_filtered['strike'].diff()
        valid_diffs = df_filtered['diff'].dropna()
        valid_diffs = valid_diffs[valid_diffs > 0]
        
        min_diff = valid_diffs.min() if len(valid_diffs) > 0 else None
        self.diff = int(min_diff) if min_diff is not None and min_diff > 0 else 100

    def find(self, key: str) -> str | int | ExchangeLiteral | None:
        '''Get value for key, filtered by exchange and symbol (underlying).'''
        df = self.df[(self.df['underlying'] == self.symbol)]
        
        if key == 'expiry_date':
            expiries = df['expiry_date'].dropna().unique()
            today = datetime.today().date()
            parsed = []
            for e in expiries:
                try:
                    dt = datetime.strptime(e.upper(), '%d%b%Y').date()
                    parsed.append((abs((dt - today).days), e))
                except ValueError:
                    pass
            if parsed:
                return sorted(parsed)[0][1]
            return None
        
        row = df.iloc[0] if len(df) > 0 else None
        return row[key] if row is not None and key in row else None

    def atm_strike(self, ltp: float) -> int:
        '''Calculate ATM strike using self.diff.'''
        strike = int(ltp / self.diff) * self.diff
        return strike if ltp >= strike + self.diff / 2 else strike - self.diff

    def filter_by_moneyness(
        self,
        ltp: float,
        distance: int,
        c_or_p: OptionsLiteral,
    ) -> list[SymbolType]:
        '''Get rows by distance from ATM.'''
        atm = self.atm_strike(ltp)
        target_strike = atm + (distance * self.diff) if c_or_p == 'CE' else atm - (distance * self.diff)
        
        df = self.df[
            (self.df['underlying'] == self.symbol) &
            (self.df['option_type'] == c_or_p)
        ]
        
        row = df[df['strike'] == target_strike]
        if len(row) > 0:
            return [row.iloc[0].to_dict()]
        return []

    def get_atm_rows(
        self,
        ltp: float,
        c_or_p: OptionsLiteral,
    ) -> list[SymbolType]:
        '''Get DEPTH rows on each side of ATM.'''
        atm = self.atm_strike(ltp)
        
        df = self.df[
            (self.df['underlying'] == self.symbol) &
            (self.df['option_type'] == c_or_p)
        ].copy()
        
        df['distance'] = abs(df['strike'] - atm)
        df = df.nsmallest(DEPTH, 'distance')
        
        if c_or_p == 'CE':
            df = df.sort_values('strike', ascending=False)
        else:
            df = df.sort_values('strike', ascending=True)
        
        # Keep only standard columns for return
        cols = ['exchange', 'tradingsymbol', 'token', 'expiry_date', 'strike', 
                'option_type', 'lot_size', 'ws_token']
        df = df.drop(columns=['distance', 'underlying', 'contract_value_num'], errors='ignore')
        return df[cols].to_dict('records')

    def to_ws_tokens(self, rows: list[SymbolType]) -> list[str]:
        '''Convert Symbol rows to ws_tokens (just token ID).'''
        return [str(row['token']) for row in rows]

    def from_ws_token(self, ws_token: str) -> SymbolType | None:
        '''Reverse lookup: ws_token to Symbol.'''
        row = self.df[self.df['token'].astype(str) == str(ws_token)]
        return row.iloc[0].to_dict() if len(row) > 0 else None

    def find_closest_premium(
        self,
        quotes: dict[str, float],
        premium: float,
        c_or_p: OptionsLiteral,
    ) -> list[SymbolType]:
        '''Find Symbol(s) with premium closest to target.'''
        filtered = {}
        for ts, ltp in quotes.items():
            row = self.df[self.df['tradingsymbol'] == ts]
            if len(row) > 0 and row.iloc[0]['option_type'] == c_or_p:
                filtered[ts] = ltp
        
        if not filtered:
            return []
        
        closest_ts = min(filtered, key=lambda ts: abs(filtered[ts] - premium))
        row = self.df[self.df['tradingsymbol'] == closest_ts]
        return [row.iloc[0].to_dict()] if len(row) > 0 else []

    def _rename_columns(self, df: pd.DataFrame, override: dict) -> pd.DataFrame:
        '''Internal: rename columns using override mapping.'''
        return df.rename(columns=override)


# =============================================================================
# Example: python broker_ai/delta/symbols.py
# =============================================================================

if __name__ == '__main__':
    symbols = Symbol(exchange='DELTA', symbol='BTC')
    
    print(f'Exchange: {symbols.exchange}')
    print(f'Underlying: {symbols.symbol}')
    print(f'Diff: {symbols.diff}')
    print(f'Rows: {len(symbols.df)}')
    print(f'Expiry: {symbols.find('expiry_date')}')
    print(f'First row: {symbols.df.iloc[0].to_dict() if len(symbols.df) > 0 else None}')