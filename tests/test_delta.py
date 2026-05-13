import pytest
from unittest.mock import MagicMock, patch


class TestDeltaAuthenticate:
    def test_authenticate_success(self, delta_broker):
        result = delta_broker.authenticate()
        assert result["status"] == "authenticated"
        assert result["products_count"] == 2

    def test_authenticate_failure(self, delta_broker, mock_delta_api):
        mock_delta_api.get_products.return_value = []
        result = delta_broker.authenticate()
        assert result is None


class TestDeltaOrders:
    def test_orders_returns_standardized(self, delta_broker):
        orders = delta_broker.orders
        assert len(orders) == 1
        assert orders[0]["order_id"] == "ord_001"
        assert orders[0]["symbol"] == "C-BTC-95000-310726"

    def test_orders_empty(self, delta_broker, mock_delta_api):
        mock_delta_api.get_active_orders.return_value = []
        assert delta_broker.orders == [{}]

    def test_order_place_returns_order_id(self, delta_broker):
        order_id = delta_broker.order_place(
            symbol="C-BTC-95000-310726",
            side="BUY",
            quantity=100,
        )
        assert order_id == "ord_new_001"

    def test_order_place_with_tag(self, delta_broker):
        order_id = delta_broker.order_place(
            symbol="P-BTC-95000-310726",
            side="SELL",
            quantity=50,
            tag="btc_opt_sell",
        )
        assert order_id == "ord_new_001"

    def test_order_cancel_returns_response(self, delta_broker):
        result = delta_broker.order_cancel(order_id="ord_001")
        assert result is not None

    def test_order_modify_returns_response(self, delta_broker):
        result = delta_broker.order_modify(order_id="ord_001", quantity=200, price=3400)
        assert result is not None


class TestDeltaPositions:
    def test_positions_returns_list(self, delta_broker):
        positions = delta_broker.positions
        assert len(positions) == 1
        assert positions[0]["symbol"] == "C-BTC-95000-310726"
        assert positions[0]["quantity"] == 100.0

    def test_positions_empty(self, delta_broker, mock_delta_api):
        mock_delta_api.get_positions.return_value = []
        assert delta_broker.positions == [{}]


class TestDeltaTrades:
    def test_trades_returns_list(self, delta_broker):
        trades = delta_broker.trades
        assert len(trades) == 1
        assert trades[0]["trade_id"] == "trd_001"
        assert trades[0]["symbol"] == "C-BTC-95000-310726"

    def test_trades_empty(self, delta_broker, mock_delta_api):
        mock_delta_api.get_fills.return_value = []
        assert delta_broker.trades == []


class TestDeltaMargins:
    def test_margins_returns_balances(self, delta_broker):
        margins = delta_broker.margins
        assert "balances" in margins
        assert margins["balances"][0]["asset"] == "BTC"
        assert margins["balances"][0]["available_balance"] == "1.0"

    def test_margins_empty(self, delta_broker, mock_delta_api):
        mock_delta_api.get_wallet_balances.return_value = []
        assert delta_broker.margins == {}


class TestDeltaMarketData:
    def test_ltp_returns_price(self, delta_broker):
        ltp = delta_broker.ltp("C-BTC-95000-310726")
        assert ltp["symbol"] == "C-BTC-95000-310726"
        assert ltp["ltp"] == 3200.50

    def test_ltp_empty(self, delta_broker, mock_delta_api):
        mock_delta_api.get_ticker.return_value = {}
        assert delta_broker.ltp("UNKNOWN") == {}

    def test_get_products_returns_list(self, delta_broker):
        products = delta_broker.get_products()
        assert len(products) == 2

    def test_get_products_filtered_by_type(self, delta_broker):
        products = delta_broker.get_products(contract_types="call_options")
        assert len(products) == 2

    def test_historical_returns_candles(self, delta_broker):
        candles = delta_broker.historical("BTCUSD")
        assert len(candles) == 2
        assert candles[0]["open"] == 79000.0
        assert candles[0]["close"] == 79300.0

    def test_orderbook_returns_bids_asks(self, delta_broker):
        ob = delta_broker.orderbook("BTCUSD")
        assert "bids" in ob
        assert "asks" in ob


class TestDeltaInstruments:
    def test_instrument_symbol(self, delta_broker, mock_delta_api):
        mock_delta_api.get_product.return_value = {"symbol": "C-BTC-95000-310726", "product_id": 133633}
        result = delta_broker.instrument_symbol("C-BTC-95000-310726")
        assert result["symbol"] == "C-BTC-95000-310726"

    def test_profile(self, delta_broker, mock_delta_api):
        mock_delta_api._request.return_value = {"user": {"id": 1, "email": "test@test.com"}}
        profile = delta_broker.profile
        assert profile is not None
