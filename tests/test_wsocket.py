import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import json


@pytest.fixture
def wsocket():
    from broker_ai.delta.wsocket import Wsocket
    ws = Wsocket(api_key="test_key", api_secret="test_secret")
    ws.on_connect = MagicMock()
    ws.on_ticks = MagicMock()
    ws.on_close = MagicMock()
    ws.on_error = MagicMock()
    return ws


@pytest.fixture
def mock_ws_app():
    with patch("broker_ai.delta.wsocket.websocket.WebSocketApp") as mock:
        instance = MagicMock()
        mock.return_value = instance
        yield instance


class TestWsocketConnect:
    def test_connect_creates_websocketapp(self, wsocket, mock_ws_app):
        wsocket.connect(threaded=False)
        assert mock_ws_app.on_open is not None

    def test_connect_sets_callbacks(self, wsocket, mock_ws_app):
        wsocket.connect(threaded=False)
        assert mock_ws_app.on_message is not None
        assert mock_ws_app.on_error is not None
        assert mock_ws_app.on_close is not None

    def test_disconnect_closes_socket(self, wsocket, mock_ws_app):
        wsocket._ws = mock_ws_app
        wsocket.disconnect()
        mock_ws_app.close.assert_called_once()
        assert wsocket.connected is False


class TestWsocketAuth:
    def test_on_open_sends_auth(self, wsocket, mock_ws_app):
        wsocket._ws = mock_ws_app
        wsocket._on_open(mock_ws_app)
        sent = json.loads(mock_ws_app.send.call_args[0][0])
        assert sent["type"] == "key-auth"
        assert "api-key" in sent["payload"]
        assert "signature" in sent["payload"]
        assert "timestamp" in sent["payload"]

    def test_sign_returns_hex_string(self, wsocket):
        sig = wsocket._sign("1000000")
        assert isinstance(sig, str)
        assert len(sig) == 64

    def test_auth_success_triggers_on_connect(self, wsocket):
        msg = json.dumps({"type": "key-auth", "success": True, "status_code": 200})
        wsocket._on_message(None, msg)
        assert wsocket.connected is True
        wsocket.on_connect.assert_called_once()


class TestWsocketSubscribe:
    def test_subscribe_sends_subscription_message(self, wsocket):
        wsocket._ws = MagicMock()
        wsocket._connected = True
        wsocket.subscribe(["133633", "133634"])
        sent = json.loads(wsocket._ws.send.call_args[0][0])
        assert sent["type"] == "subscribe"
        assert sent["payload"]["channels"][0]["name"] == "v2/ticker"
        assert sent["payload"]["channels"][0]["symbols"] == ["133633", "133634"]

    def test_subscribe_int_tokens(self, wsocket):
        wsocket._ws = MagicMock()
        wsocket._connected = True
        wsocket.subscribe([133633])
        sent = json.loads(wsocket._ws.send.call_args[0][0])
        assert sent["payload"]["channels"][0]["symbols"] == ["133633"]

    def test_unsubscribe_sends_message(self, wsocket):
        wsocket._ws = MagicMock()
        wsocket._connected = True
        wsocket.unsubscribe(["133633"])
        sent = json.loads(wsocket._ws.send.call_args[0][0])
        assert sent["type"] == "unsubscribe"

    def test_subscribe_sends_even_when_not_yet_connected(self, wsocket):
        wsocket._ws = MagicMock()
        wsocket._connected = False
        wsocket.subscribe(["133633"])
        wsocket._ws.send.assert_called_once()


class TestWsocketTicker:
    def test_ticker_updates_ltp(self, wsocket):
        msg = json.dumps({
            "type": "v2/ticker",
            "d": [{"i": 133633, "c": "3200.50"}]
        })
        wsocket._on_message(None, msg)
        assert wsocket._ltp["133633"] == 3200.50

    def test_ticker_triggers_on_ticks(self, wsocket):
        msg = json.dumps({
            "type": "v2/ticker",
            "d": [{"i": 133633, "c": "3200.50"}]
        })
        wsocket._on_message(None, msg)
        wsocket.on_ticks.assert_called_once_with({"133633": 3200.50})

    def test_ticker_multiple_products(self, wsocket):
        msg = json.dumps({
            "type": "v2/ticker",
            "d": [
                {"i": 133633, "c": "3200.50"},
                {"i": 133634, "c": "16100.75"},
            ]
        })
        wsocket._on_message(None, msg)
        assert wsocket._ltp["133633"] == 3200.50
        assert wsocket._ltp["133634"] == 16100.75

    def test_ticker_empty_data_does_nothing(self, wsocket):
        msg = json.dumps({"type": "v2/ticker", "d": []})
        wsocket._on_message(None, msg)
        assert wsocket._ltp == {}

    def test_heartbeat_ignored(self, wsocket):
        msg = json.dumps({"type": "heartbeat"})
        wsocket._on_message(None, msg)
        assert wsocket._ltp == {}

    def test_invalid_json_ignored(self, wsocket):
        wsocket._on_message(None, "not json")
        assert wsocket._ltp == {}


class TestWsocketError:
    def test_on_error_calls_callback(self, wsocket):
        wsocket._on_error(None, "connection refused")
        wsocket.on_error.assert_called_once_with("connection refused")

    def test_on_close_sets_connected_false(self, wsocket):
        wsocket._connected = True
        wsocket._on_close(None, 1000, "bye")
        assert wsocket.connected is False
