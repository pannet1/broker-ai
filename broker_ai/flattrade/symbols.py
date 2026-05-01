from __future__ import annotations
import pandas as pd
from datetime import datetime
import os
import yaml
from pprint import pprint

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
        '''Load yaml config for column renaming and ws_token format.'''
        config_path = os.path.join(os.path.dirname(__file__), 'flattrade.yaml')
        try:
            with open(config_path, 'r') as f:
                self._config = yaml.safe_load(f)
            self._normalize_override = self._config.get('normalize', {})
            self._ws_token_format = self._config.get('ws_token_format', '{exchange}|{token}')
        except FileNotFoundError:
            self._normalize_override = {}
            self._ws_token_format = '{exchange}|{token}'

    def download(self) -> dict:
        '''Fetch raw CSV from Flattrade S3.'''
        urls = {
            'NFO': 'https://flattrade.s3.ap-south-1.amazonaws.com/scripmaster/Nfo_Index_Derivatives.csv',
            'BFO': 'https://flattrade.s3.ap-south-1.amazonaws.com/scripmaster/Bfo_Index_Derivatives.csv',
        }
        url = urls.get(self.exchange.upper())
        if not url:
            raise ValueError(f'Unsupported exchange: {self.exchange}')
        
        print(f'Downloading: {url}')
        df = pd.read_csv(url)
        return df.to_dict('records')

    def normalize(self, raw: dict | list) -> pd.DataFrame:
        '''Convert raw data to standard columns.'''
        df = pd.DataFrame(raw)
        # Rename columns using yaml config
        df = df.rename(columns=self._normalize_override)
        # Ensure standard columns exist
        df['exchange'] = self.exchange
        df['strike'] = df['strike'].fillna(0).astype(int)
        df['option_type'] = df['option_type'].fillna('')
        df['token'] = df['token'].astype(str)
        df['lot_size'] = df['lot_size'].fillna(1).astype(int)
        # Add ws_token column for websocket subscription
        df['ws_token'] = df['exchange'] + '|' + df['token'].astype(str)
        return df

    def load(self):
        '''Load from data or download and normalize.'''
        os.makedirs(self.data_path, exist_ok=True)
        data_file = os.path.join(self.data_path, f'{self.exchange}_{self.symbol}.csv')

        # Check if data exists and is fresh (today)
        if os.path.exists(data_file):
            mtime = datetime.fromtimestamp(os.path.getmtime(data_file)).date()
            if mtime == datetime.today().date():
                self.df = pd.read_csv(data_file)
                self._derive_diff()
                return

        # Download and normalize
        raw = self.download()
        self.df = self.normalize(raw)
        self._derive_diff()
        self.df.to_csv(data_file, index=False)
        print(f'Cached to: {data_file}')

    def _derive_diff(self):
        '''Derive strike interval from adjacent strikes. Filter by symbol + nearest expiry first.
        Use min diff to handle missing strikes in far OTM due to liquidity.
        '''
        # Get nearest expiry
        expiry = self.find('expiry_date')
        if not expiry:
            self.diff = 100
            return
        
        # Filter by symbol and expiry, then sort by strike
        df_filtered = self.df[
            (self.df['tradingsymbol'].str.startswith(self.symbol)) &
            (self.df['expiry_date'] == expiry) &
            (self.df['strike'] > 0)
        ].sort_values('strike')
        
        # Calculate diff between consecutive strikes (skip first row which is NaN)
        df_filtered['diff'] = df_filtered['strike'].diff()
        
        # Filter out 0 diffs (from duplicate strikes) and get min
        valid_diffs = df_filtered['diff'].dropna()
        valid_diffs = valid_diffs[valid_diffs > 0]
        
        min_diff = valid_diffs.min() if len(valid_diffs) > 0 else None
        self.diff = int(min_diff) if min_diff is not None and min_diff > 0 else 100

    def find(self, key: str) -> str | int | ExchangeLiteral | None:
        '''Get value for key, filtered by exchange and symbol.'''
        df = self.df[(self.df['exchange'] == self.exchange)]
        
        if key == 'expiry_date':
            # Filter by symbol name in tradingsymbol
            df = df[df['tradingsymbol'].str.startswith(self.symbol)]
            expiries = df['expiry_date'].dropna().unique()
            # Find nearest future expiry
            today = datetime.today().date()
            parsed = []
            for e in expiries:
                try:
                    dt = datetime.strptime(e.upper(), '%d%b%Y').date()
                    parsed.append((abs((dt - today).days), e))
                except ValueError:
                    try:
                        dt = datetime.strptime(e, '%d-%b-%Y').date()
                        parsed.append((abs((dt - today).days), e))
                    except ValueError:
                        pass
            if parsed:
                return sorted(parsed)[0][1]
            return None
        
        # For other keys, return first match filtered by symbol
        row = df[df['tradingsymbol'].str.startswith(self.symbol)].iloc[0] if len(df) > 0 else None
        return row[key] if row is not None else None

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
            (self.df['exchange'] == self.exchange) &
            (self.df['tradingsymbol'].str.startswith(self.symbol)) &
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
            (self.df['exchange'] == self.exchange) &
            (self.df['tradingsymbol'].str.startswith(self.symbol)) &
            (self.df['option_type'] == c_or_p)
        ].copy()
        
        df['distance'] = abs(df['strike'] - atm)
        df = df.nsmallest(DEPTH, 'distance')
        
        # Sort: CE descending, PE ascending
        if c_or_p == 'CE':
            df = df.sort_values('strike', ascending=False)
        else:
            df = df.sort_values('strike', ascending=True)
        
        return df.drop(columns=['distance']).to_dict('records')

    def to_ws_tokens(self, rows: list[SymbolType]) -> list[str]:
        '''Convert Symbol rows to ws_tokens.'''
        tokens = []
        for row in rows:
            tokens.append(self._ws_token_format.format(
                exchange=row['exchange'],
                token=row['token']
            ))
        return tokens

    def from_ws_token(self, ws_token: str) -> SymbolType | None:
        '''Reverse lookup: ws_token to Symbol.'''
        parts = ws_token.split('|')
        if len(parts) == 2:
            exchange, token = parts
        else:
            exchange = self.exchange
            token = ws_token
        
        row = self.df[
            (self.df['exchange'] == exchange) &
            (self.df['token'].astype(str) == str(token))
        ]
        return row.iloc[0].to_dict() if len(row) > 0 else None

    def find_closest_premium(
        self,
        quotes: dict[str, float],
        premium: float,
        c_or_p: OptionsLiteral,
    ) -> list[SymbolType]:
        '''Find Symbol(s) with premium closest to target. Returns list (empty if none).'''
        # Filter quotes by option type
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
# Example: python broker_ai/flattrade/symbols.py
# =============================================================================

if __name__ == '__main__':
    # Default data_path: broker_ai/data/
    symbols = Symbol(exchange='NFO', symbol='NIFTY')
    # Or custom path: Symbol(exchange='NFO', symbol='NIFTY', data_path='/custom/path')
    ltp = 24156.35
    
    print('\n--- attributes ---')
    pprint({'exchange': symbols.exchange, 'symbol': symbols.symbol})
    pprint({'diff': symbols.diff, 'rows': len(symbols.df)})
    pprint({'ws_token in df': 'ws_token' in symbols.df.columns})
    
    print('\n--- find(key) ---')
    pprint({'expiry_date': symbols.find('expiry_date')})
    pprint({'lot_size': symbols.find('lot_size')})
    
    print('\n--- atm_strike(ltp) ---')
    pprint({'ltp': ltp, 'atm_strike': symbols.atm_strike(ltp)})
    
    print('\n--- get_atm_rows(ltp, CE) ---')
    rows = symbols.get_atm_rows(ltp, 'CE')
    pprint({'rows_returned': len(rows)})
    print('first row:')
    pprint(rows[0])
    
    print('\n--- to_ws_tokens(rows[:3]) ---')
    tokens = symbols.to_ws_tokens(rows[:3])
    pprint(tokens)
    
    print('\n--- from_ws_token(tokens[0]) ---')
    symbol = symbols.from_ws_token(tokens[0])
    pprint(symbol)
    
    print('\n--- filter_by_moneyness(ltp, +3, CE) ---')
    filtered = symbols.filter_by_moneyness(ltp, 3, 'CE')
    pprint(filtered[0] if filtered else 'None')
    
    print('\n--- find_closest_premium(quotes, 180, CE) ---')
    quotes = {row['tradingsymbol']: 150 + i * 10 for i, row in enumerate(rows[:5])}
    pprint({'quotes': quotes})
    closest = symbols.find_closest_premium(quotes, 180, 'CE')
    pprint({'closest': closest[0] if closest else 'None'})
