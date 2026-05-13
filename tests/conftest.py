import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import yaml

SAMPLE_BTC_CALL = {
    "product_id": 133633,
    "symbol": "C-BTC-95000-310726",
    "contract_type": "call_options",
    "strike_price": "95000",
    "underlying_asset": {"symbol": "BTC"},
    "settlement_time": "2026-07-31T12:00:00Z",
    "contract_value": "0.001",
    "mark_price": "3200.50",
    "description": "BTC Call",
}

SAMPLE_BTC_PUT = {
    "product_id": 133634,
    "symbol": "P-BTC-95000-310726",
    "contract_type": "put_options",
    "strike_price": "95000",
    "underlying_asset": {"symbol": "BTC"},
    "settlement_time": "2026-07-31T12:00:00Z",
    "contract_value": "0.001",
    "mark_price": "16100.75",
    "description": "BTC Put",
}

SAMPLE_BTC_PERP = {
    "product_id": 27,
    "symbol": "BTCUSD",
    "contract_type": "perpetual_futures",
    "underlying_asset": {"symbol": "BTC"},
    "settlement_time": None,
    "contract_value": "0.001",
    "mark_price": "79200.00",
    "description": "BTC Perpetual",
}

BTC_OPTION_PRODUCTS = [SAMPLE_BTC_CALL, SAMPLE_BTC_PUT]

SAMPLE_ORDER = {
    "id": "ord_001",
    "symbol": "C-BTC-95000-310726",
    "side": "buy",
    "size": "100",
    "limit_price": "3200",
    "order_type": "limit_order",
    "state": "open",
    "filled_size": "0",
    "average_price": "0",
    "product_type": "carryforward",
    "created_at": "2026-05-13T10:00:00Z",
    "updated_at": "2026-05-13T10:00:00Z",
}

SAMPLE_ORDERS = [SAMPLE_ORDER]

SAMPLE_POSITION = {
    "symbol": "C-BTC-95000-310726",
    "product_id": 133633,
    "quantity": "100",
    "side": "BUY",
    "average_price": "3150.00",
    "mark_price": "3200.50",
    "unrealized_pnl": "50.50",
    "realized_pnl": "0",
    "leverage": 10,
    "margin": "31500",
    "liquidation_price": "28000",
}

SAMPLE_POSITIONS = [SAMPLE_POSITION]

SAMPLE_TRADE = {
    "id": "trd_001",
    "order_id": "ord_001",
    "symbol": "C-BTC-95000-310726",
    "side": "buy",
    "size": "100",
    "price": "3150.00",
    "timestamp": "2026-05-13T10:00:00Z",
}

SAMPLE_TRADES = [SAMPLE_TRADE]

SAMPLE_CANDLES = [
    {"time": 1715500000, "open": "79000", "high": "79500", "low": "78900", "close": "79300", "volume": "100.5"},
    {"time": 1715503600, "open": "79300", "high": "79800", "low": "79200", "close": "79600", "volume": "85.2"},
]

BTC_OPTION_RAW = {
    "result": [
        {
            "id": 133633,
            "symbol": "C-BTC-95000-310726",
            "contract_type": "call_options",
            "strike_price": "95000",
            "underlying_asset": {"symbol": "BTC"},
            "settlement_time": "2026-07-31T12:00:00Z",
            "contract_value": "0.001",
        },
        {
            "id": 133634,
            "symbol": "P-BTC-95000-310726",
            "contract_type": "put_options",
            "strike_price": "95000",
            "underlying_asset": {"symbol": "BTC"},
            "settlement_time": "2026-07-31T12:00:00Z",
            "contract_value": "0.001",
        },
    ]
}


@pytest.fixture
def mock_delta_api():
    mock = MagicMock()
    mock.get_products.return_value = BTC_OPTION_PRODUCTS
    mock.get_tickers.return_value = BTC_OPTION_PRODUCTS
    mock.get_active_orders.return_value = SAMPLE_ORDERS
    mock.get_positions.return_value = SAMPLE_POSITIONS
    mock.get_fills.return_value = SAMPLE_TRADES
    mock.get_wallet_balances.return_value = [{"asset": "BTC", "balance": "1.5", "available_balance": "1.0"}]
    mock.get_ticker.return_value = {"symbol": "C-BTC-95000-310726", "last_price": "3200.50", "change_24h": "5.2", "volume_24h": "10000"}
    mock.get_historical_candles.return_value = SAMPLE_CANDLES
    mock.get_orderbook.return_value = {"bids": [["79000", "1.5"]], "asks": [["79100", "2.0"]]}
    mock.place_order.return_value = {"id": "ord_new_001", "client_oid": "my_tag"}
    mock.cancel_order.return_value = {"success": True, "result": {"id": "ord_001", "state": "cancelled"}}
    mock.edit_order.return_value = {"success": True, "result": {"id": "ord_001", "state": "open"}}
    return mock


@pytest.fixture
def delta_broker(mock_delta_api):
    with patch("broker_ai.delta.delta.DeltaAPI", return_value=mock_delta_api):
        from broker_ai.delta.delta import Delta
        broker = Delta(api_key="test_key", api_secret="test_secret")
        return broker


@pytest.fixture
def sample_config():
    return {
        "delta": {
            "uid": 95665425,
            "username": "test-user",
            "api_key": "ZBwPR3dsMVEy03YnP1HgtXGKvryiYp",
            "api_secret": "wYkkFHUCp3aDkItR9HKgYbZOlVNYQuNo8UoF3NeU3KEKHkQgRNZrFeJxLoW9",
            "2fa": "5QXXNLJ3G4RMI5OE",
        }
    }


@pytest.fixture
def temp_data_dir(tmp_path):
    return tmp_path
