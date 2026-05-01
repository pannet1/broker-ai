from __future__ import annotations
from typing import Protocol


class Wsocket(Protocol):
    '''
    Websocket protocol for LTP streaming.
    
    Methods have same names across brokers.
    Parameters handled via *args, **kwargs for broker-specific needs.
    
    NOTE: Not all callbacks available in every broker:
    - Flattrade: on_connect, on_ticks, on_order, on_close, on_error
    - Zerodha:   on_connect, on_ticks, on_close, on_error, 
                 on_reconnect, on_noreconnect (on_order NOT built-in)
    
    Example:
        # Flattrade
        from broker_ai.flattrade.wsocket import Wsocket
        ws = Wsocket(api)
        ws.on_connect = lambda: ws.subscribe(['NFO|12345'])
        ws.on_ticks = lambda ltp: print(ltp)
        ws.connect()
        
        # Zerodha
        from broker_ai.zerodha.wsocket import Wsocket
        ws = Wsocket(api)
        ws.on_connect = lambda: ws.subscribe([25625])
        ws.on_ticks = lambda ltp: print(ltp)
        ws.connect()
    '''
    
    # --- Properties ---
    
    @property
    def ltp(self) -> dict:
        '''Current LTP dict: {ws_token: ltp}.'''
        ...
    
    @property
    def connected(self) -> bool:
        '''Connection status.'''
        ...
    
    # --- Core Methods (all brokers) ---
    
    def subscribe(self, *args, **kwargs) -> None:
        '''Subscribe to tokens.'''
        ...
    
    def unsubscribe(self, *args, **kwargs) -> None:
        '''Unsubscribe from tokens.'''
        ...
    
    def connect(self, *args, **kwargs) -> None:
        '''Connect to websocket.'''
        ...
    
    def disconnect(self, *args, **kwargs) -> None:
        '''Disconnect from websocket.'''
        ...
    
    # --- Callbacks (broker-specific - set by user) ---
    
    def on_connect(self, *args, **kwargs) -> None: ...
    def on_ticks(self, *args, **kwargs) -> None: ...
    def on_close(self, *args, **kwargs) -> None: ...
    def on_error(self, *args, **kwargs) -> None: ...
    def on_reconnect(self, *args, **kwargs) -> None: ...
    def on_noreconnect(self, *args, **kwargs) -> None: ...
    def on_order(self, *args, **kwargs) -> None: ...  # Flattrade only