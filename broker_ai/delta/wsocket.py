from __future__ import annotations
import json
import time
import hashlib
import hmac
import threading
import websocket
from typing import Callable


class Wsocket:
    def __init__(self, api_key: str | None = None, api_secret: str | None = None):
        self._api_key = api_key
        self._api_secret = api_secret
        self._ltp: dict[str, float] = {}
        self._connected: bool = False
        self._ws: websocket.WebSocketApp | None = None
        self._thread: threading.Thread | None = None
        self._should_stop: bool = False
        self._use_private: bool = bool(api_key and api_secret)
        self._public_url = "wss://public-socket.india.delta.exchange"
        self._private_url = "wss://socket.india.delta.exchange"

        self.on_connect: Callable = lambda: None
        self.on_ticks: Callable = lambda ltp: None
        self.on_close: Callable = lambda: None
        self.on_error: Callable = lambda err: None
        self.on_order: Callable = lambda msg: None

    @property
    def ltp(self) -> dict:
        return self._ltp

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self, threaded: bool = True) -> None:
        self._should_stop = False
        url = self._private_url if self._use_private else self._public_url
        self._ws = websocket.WebSocketApp(
            url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self._ws.on_open = self._on_open
        if threaded:
            self._thread = threading.Thread(target=self._ws.run_forever, daemon=True)
            self._thread.start()
        else:
            self._ws.run_forever()

    def disconnect(self) -> None:
        self._should_stop = True
        if self._ws:
            self._ws.close()
        self._connected = False

    def subscribe(self, tokens: list[str]) -> None:
        ch = "v2/ticker" if self._use_private else "ticker"
        symbols = [str(t) for t in tokens]
        payload = {
            "type": "subscribe",
            "payload": {
                "channels": [{"name": ch, "symbols": symbols}]
            }
        }
        self._send(payload)

    def unsubscribe(self, tokens: list[str]) -> None:
        ch = "v2/ticker" if self._use_private else "ticker"
        symbols = [str(t) for t in tokens]
        payload = {
            "type": "unsubscribe",
            "payload": {
                "channels": [{"name": ch, "symbols": symbols}]
            }
        }
        self._send(payload)

    def _send(self, data: dict) -> None:
        if self._ws:
            self._ws.send(json.dumps(data))

    def _sign(self, timestamp: str) -> str:
        message = bytes(f"GET{timestamp}/live", "utf-8")
        secret = bytes(self._api_secret, "utf-8") if self._api_secret else b""
        return hmac.new(secret, message, hashlib.sha256).hexdigest()

    def _authenticate(self) -> None:
        if not self._api_key or not self._api_secret:
            self._connected = True
            self.on_connect()
            return
        timestamp = str(int(time.time()))
        signature = self._sign(timestamp)
        self._send({
            "type": "key-auth",
            "payload": {
                "api-key": self._api_key,
                "signature": signature,
                "timestamp": timestamp,
            }
        })

    def _on_open(self, ws) -> None:
        self._authenticate()

    def _on_close(self, ws, close_status_code, close_msg) -> None:
        self._connected = False
        self.on_close()

    def _on_error(self, ws, error) -> None:
        self.on_error(str(error))

    def _on_message(self, ws, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        t = msg.get("type")

        if t == "key-auth":
            if msg.get("success"):
                self._connected = True
                self.on_connect()
            else:
                self.on_error(msg.get("message", "auth failed"))

        elif t == "subscriptions":
            if not self._connected:
                self._connected = True
                self.on_connect()

        elif t in ("ticker", "v2/ticker"):
            self._handle_ticker(msg)

        elif t == "heartbeat":
            pass

    def _handle_ticker(self, msg: dict) -> None:
        data = msg.get("d", [])
        if not data:
            return
        if isinstance(data, dict):
            data = [data]

        updated = False
        for tick in data:
            pid = tick.get("i")
            if not pid:
                continue
            close = tick.get("c")
            if close is not None:
                self._ltp[str(pid)] = float(close)
                updated = True
                continue
            ohlc = tick.get("ohlc")
            if ohlc and len(ohlc) >= 4 and ohlc[3] is not None:
                self._ltp[str(pid)] = float(ohlc[3])
                updated = True
                continue
            m = tick.get("m")
            if m is not None:
                self._ltp[str(pid)] = float(m)
                updated = True

        if updated:
            self.on_ticks(self._ltp)
