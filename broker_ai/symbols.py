from __future__ import annotations
from typing import Protocol, Literal, TypedDict, Callable, overload
import pandas as pd

DEPTH = 25  # always 25 strikes on each side of ATM

# Indian exchanges
IndianExchangeLiteral = Literal["NSE", "BSE", "BFO", "NFO", "MCX", "NCDEX"]

# Crypto exchanges
CryptoExchangeLiteral = Literal[
    "DELTA",    # Delta Exchange
    "BYBIT",    # Bybit
    "DERIBIT",  # Deribit
    "BINANCE",  # Binance
    "OKX",      # OKX
]

# Combined
ExchangeLiteral = IndianExchangeLiteral | CryptoExchangeLiteral
OptionsLiteral = Literal["CE", "PE"]

SymbolKey = Literal[
    "expiry_date",
    "lot_size",
    "strike",
    "option_type",
    "tradingsymbol",
    "token",
    "exchange",
    "ws_token",
]


class Symbol(TypedDict):
    """Symbol metadata from master CSV."""

    exchange: ExchangeLiteral
    tradingsymbol: str
    token: str | int
    expiry_date: str
    strike: int
    option_type: OptionsLiteral | None
    lot_size: int
    ws_token: str  # broker-specific format, e.g. 'NFO|12345' or '12345'


def post(func: Callable) -> Callable:
    """
    Decorator to rename response keys after normalize.
    Uses self._normalize_override from yaml config.
    """
    name = func.__name__

    def f(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        override = getattr(self, "_normalize_override", None)
        if override:
            return self._rename_columns(result, override)
        return result

    return f


class Symbols(Protocol):
    exchange: ExchangeLiteral
    symbol: str
    diff: int  # derived from data after download
    df: pd.DataFrame

    def __init__(self, exchange: ExchangeLiteral, symbol: str) -> None:
        """
        Initialize and load symbol data.
        Must call self.load() to:
            1. download() raw data
            2. normalize() to standard columns (via @post hook)
            3. derive self.diff from adjacent strike prices
            4. populate self.df
        """
        ...

    def download(self) -> dict:
        """
        Fetch raw data from broker API.

        Returns:
            dict - raw broker response
        """

    @post
    def normalize(self, raw: dict) -> pd.DataFrame:
        """
        Convert raw broker data to standard format.
        Column renaming handled by @post hook via yaml config.

        Expected output columns:
            exchange, tradingsymbol, token, expiry_date,
            strike, option_type, lot_size

        Returns:
            pd.DataFrame with normalized columns
        """

    def load(self) -> None:
        """
        Load df from local cache if fresh, else download and normalize.
        Sets self.diff from adjacent strike prices.
        """

    @overload
    def find(self, key: Literal["expiry_date"]) -> str: ...
    @overload
    def find(self, key: Literal["lot_size"] | Literal["strike"]) -> int: ...
    @overload
    def find(self, key: Literal["tradingsymbol"] | Literal["option_type"]) -> str: ...
    @overload
    def find(self, key: Literal["exchange"]) -> ExchangeLiteral: ...
    @overload
    def find(self, key: Literal["token"]) -> str | int: ...
    @overload
    def find(self, key: Literal["ws_token"]) -> str: ...

    def find(self, key: SymbolKey) -> str | int | ExchangeLiteral | None:
        """
        Get value for key using self.exchange and self.symbol to filter.
        If key is 'expiry_date', returns nearest future expiry.
        Otherwise returns first matching value.

        Args:
            key: Literal['expiry_date', 'lot_size', 'strike', 'option_type',
                  'tradingsymbol', 'token', 'exchange', 'ws_token']

        Returns:
            Value for key, or None
        """

    def atm_strike(self, ltp: float) -> int:
        """
        Calculate ATM strike from underlying LTP using self.diff.

        Args:
            ltp: last traded price of underlying

        Returns:
            ATM strike as int
        """

    def filter_by_moneyness(
        self,
        ltp: float,
        distance: int,
        c_or_p: OptionsLiteral,
    ) -> list[Symbol]:
        """
        Filter from ATM ± DEPTH rows by moneyness distance.
        +distance = OTM, -distance = ITM.

        Args:
            ltp: last traded price of underlying
            distance: steps from ATM (e.g. +3 for ATM+3, -2 for ATM-2)
            c_or_p: 'CE' for calls, 'PE' for puts

        Returns:
            list[Symbol] matching moneyness distance
        """

    def get_atm_rows(
        self,
        ltp: float,
        c_or_p: OptionsLiteral,
    ) -> list[Symbol]:
        """
        Get DEPTH rows on one side of ATM for LTP subscription.
        DEPTH=25 fixed.

        Args:
            ltp: last traded price of underlying
            c_or_p: 'CE' for calls, 'PE' for puts

        Returns:
            list[Symbol] (25 rows) sorted by distance from ATM
        """

    def to_ws_tokens(self, rows: list[Symbol]) -> list[str]:
        """
        Convert Symbol rows to websocket tokens in broker-specific format.

        Flattrade:  format = {exchange}|{token} (e.g. 'NFO|12345')
        Zerodha:    format = {token} (e.g. '12345')

        Broker format loaded from yaml config.

        Args:
            rows: list of Symbol dicts

        Returns:
            list[str] - ws_tokens for subscribe
        """

    def from_ws_token(self, ws_token: str) -> Symbol | None:
        """
        Reverse lookup: ws_token to Symbol.
        Used to build lookup dict before trading starts.

        Args:
            ws_token: broker-format token (e.g. 'NFO|12345')

        Returns:
            Symbol or None
        """

    def find_closest_premium(
        self,
        quotes: dict[str, float],
        premium: float,
        c_or_p: OptionsLiteral,
    ) -> list[Symbol]:
        """
        Find Symbol(s) with premium closest to target.

        Args:
            quotes: {tradingsymbol: ltp} dict
            premium: target premium value
            c_or_p: filter by option type

        Returns:
            list[Symbol] - Symbol with closest premium (empty list if none)
        """

    def _rename_columns(self, df: pd.DataFrame, override: dict) -> pd.DataFrame:
        """
        Rename DataFrame columns using override mapping.
        Internal method used by @post decorator.
        """
        ...

