from __future__ import annotations
from .NorenApi import NorenApi, FeedType


class Wsocket:
    '''
    Flattrade websocket implementation.
    
    Callbacks: on_connect, on_ticks, on_order, on_close, on_error
    
    Usage:
        api = NorenApi()
        api.login(...)
        
        ws = Wsocket(api)
        ws.on_connect = lambda: ws.subscribe(['NFO|12345'])
        ws.on_ticks = lambda ltp: print(ltp)
        ws.connect()
    '''
    
    def __init__(self, api: NorenApi):
        self._api = api
        self._ltp: dict[str, float] = {}
        self._connected: bool = False
        
        # Default callbacks - user overrides these
        self.on_connect = lambda: None
        self.on_ticks = lambda ltp: None
        self.on_order = lambda msg: None
        self.on_close = lambda: None
        self.on_error = lambda err: None
    
    @property
    def ltp(self) -> dict:
        '''Current LTP dict: {ws_token: ltp}.'''
        return self._ltp
    
    @property
    def connected(self) -> bool:
        '''Connection status.'''
        return self._connected
    
    def connect(self) -> None:
        '''Connect to websocket.'''
        self._api.start_websocket(
            subscribe_callback=self._on_ticks,
            order_update_callback=self._on_order,
            socket_open_callback=self._on_open,
            socket_close_callback=self._on_close,
            socket_error_callback=self._on_error,
        )
    
    def disconnect(self) -> None:
        '''Disconnect from websocket.'''
        self._api.close_websocket()
        self._connected = False
    
    def subscribe(self, tokens: list[str]) -> None:
        '''Subscribe to ws_tokens (e.g. ['NFO|12345']).'''
        token_str = '#'.join(tokens)
        self._api.subscribe(token_str, feed_type=FeedType.SNAPQUOTE)
    
    def unsubscribe(self, tokens: list[str]) -> None:
        '''Unsubscribe from ws_tokens.'''
        token_str = '#'.join(tokens)
        self._api.unsubscribe(token_str, feed_type=FeedType.SNAPQUOTE)
    
    # --- Internal callbacks ---
    
    def _on_open(self) -> None:
        self._connected = True
        self.on_connect()
    
    def _on_close(self) -> None:
        self._connected = False
        self.on_close()
    
    def _on_error(self, error) -> None:
        self.on_error(str(error))
    
    def _on_ticks(self, data: dict | list) -> None:
        '''Process tick data.'''
        if isinstance(data, dict):
            if data.get('lp'):
                ws_token = f'{data.get('e')}|{data.get('tk')}'
                self._ltp[ws_token] = data['lp']
                self.on_ticks(self._ltp)
        elif isinstance(data, list):
            for tick in data:
                if tick.get('lp'):
                    ws_token = f'{tick.get('e')}|{tick.get('tk')}'
                    self._ltp[ws_token] = tick['lp']
            if data:
                self.on_ticks(self._ltp)
    
    def _on_order(self, message: dict) -> None:
        '''Process order update.'''
        self.on_order(message)