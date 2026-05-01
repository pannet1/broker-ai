from __future__ import annotations


class Wsocket:
    '''
    Zerodha Kite websocket implementation.
    
    Callbacks: on_connect, on_ticks, on_close, on_error, on_reconnect, on_noreconnect
    Note: on_order NOT built-in - handle separately via REST API
    
    Usage:
        from kiteconnect import KiteTick
        
        api = KiteTick(api_key, access_token)
        ws = Wsocket(api)
        ws.on_connect = lambda: ws.subscribe([25625, 11000])
        ws.on_ticks = lambda ltp: print(ltp)
        ws.connect()
    '''
    
    def __init__(self, api):
        self._api = api
        self._ltp: dict = {}
        self._connected: bool = False
        
        # Default callbacks - user overrides these
        self.on_connect = lambda: None
        self.on_ticks = lambda ltp: None
        self.on_close = lambda: None
        self.on_error = lambda err: None
        self.on_reconnect = lambda attempts: None
        self.on_noreconnect = lambda: None
        
        # Pending subscription changes
        self._subscribe_pending: list = []
        self._unsubscribe_pending: list = []
    
    @property
    def ltp(self) -> dict:
        '''Current LTP dict: {token: ltp}.'''
        return self._ltp
    
    @property
    def connected(self) -> bool:
        '''Connection status.'''
        return self._connected
    
    def connect(self, threaded: bool = True) -> None:
        '''Connect to websocket.'''
        self._api.on_ticks = self._on_ticks
        self._api.on_connect = self._on_open
        self._api.on_close = self._on_close
        self._api.on_error = self._on_error
        self._api.on_reconnect = self._on_reconnect
        self._api.on_noreconnect = self._on_noreconnect
        
        self._api.connect(threaded=threaded)
    
    def disconnect(self) -> None:
        '''Disconnect from websocket.'''
        self._api.stop()
        self._connected = False
    
    def subscribe(self, tokens: list[int | str]) -> None:
        '''Subscribe to tokens (e.g. [25625, 11000]).'''
        self._subscribe_pending = list(tokens)
    
    def unsubscribe(self, tokens: list[int | str]) -> None:
        '''Unsubscribe from tokens.'''
        self._unsubscribe_pending = list(tokens)
    
    # --- Internal callbacks ---
    
    def _on_open(self, ws, response) -> None:
        self._connected = True
        self.on_connect()
    
    def _on_close(self, ws, code, reason) -> None:
        self._connected = False
        self.on_close()
    
    def _on_error(self, ws, code, reason) -> None:
        self.on_error(f'{code} - {reason}')
    
    def _on_reconnect(self, ws, attempts_count) -> None:
        self.on_reconnect(attempts_count)
    
    def _on_noreconnect(self, ws) -> None:
        self.on_noreconnect()
    
    def _on_ticks(self, ws, ticks: list) -> None:
        '''Process tick data and handle pending subscriptions.'''
        for tick in ticks:
            token = tick.get('instrument_token')
            
            # Try depth price (for options in full mode)
            if 'depth' in tick and tick['depth']['buy']:
                self._ltp[token] = tick['depth']['buy'][-1]['price']
            # Fallback to last price
            elif 'last_price' in tick:
                self._ltp[token] = tick['last_price']
        
        if ticks:
            self.on_ticks(self._ltp)
        
        # Handle pending subscription changes on tick
        if self._unsubscribe_pending:
            ws.unsubscribe(self._unsubscribe_pending)
            self._unsubscribe_pending = []
        elif self._subscribe_pending:
            ws.subscribe(self._subscribe_pending)
            ws.set_mode(ws.MODE_FULL, self._subscribe_pending)
            self._subscribe_pending = []