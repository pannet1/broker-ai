import pytest
from broker_ai.delta.api_helper import (
    generate_signature,
    get_side,
    get_order_type,
    get_product_type,
    make_order_place_args,
    make_order_modify_args,
    post_order_hook,
    post_trade_hook,
)


class TestGenerateSignature:
    def test_hmac_sha256_signature(self):
        sig = generate_signature("secret", "message")
        assert isinstance(sig, str)
        assert len(sig) == 64

    def test_different_secret_different_signature(self):
        sig1 = generate_signature("secret1", "message")
        sig2 = generate_signature("secret2", "message")
        assert sig1 != sig2

    def test_different_message_different_signature(self):
        sig1 = generate_signature("secret", "msg1")
        sig2 = generate_signature("secret", "msg2")
        assert sig1 != sig2


class TestGetSide:
    def test_buy_uppercase(self):
        assert get_side("BUY") == "buy"

    def test_sell_uppercase(self):
        assert get_side("SELL") == "sell"

    def test_buy_lowercase(self):
        assert get_side("buy") == "buy"

    def test_sell_mixed_case(self):
        assert get_side("Sell") == "sell"


class TestGetOrderType:
    def test_limit(self):
        assert get_order_type("LIMIT") == "limit_order"

    def test_market(self):
        assert get_order_type("MARKET") == "market_order"

    def test_stop_limit(self):
        assert get_order_type("STOP_LIMIT") == "stop_order"

    def test_stop_market(self):
        assert get_order_type("STOP_MARKET") == "stop_order"

    def test_unknown_defaults_to_limit(self):
        assert get_order_type("UNKNOWN") == "limit_order"


class TestGetProductType:
    def test_mis(self):
        assert get_product_type("MIS") == "intrady"

    def test_cnc(self):
        assert get_product_type("CNC") == "delivery"

    def test_nrml(self):
        assert get_product_type("NRML") == "carryforward"

    def test_unknown_defaults_to_carryforward(self):
        assert get_product_type("UNKNOWN") == "carryforward"


class TestMakeOrderPlaceArgs:
    def test_minimal_market_order(self):
        args = make_order_place_args(symbol="C-BTC-95000-310726", side="BUY", quantity=100)
        assert args["symbol"] == "C-BTC-95000-310726"
        assert args["side"] == "buy"
        assert args["order_type"] == "market_order"
        assert args["size"] == "100"
        assert args["product_type"] == "carryforward"

    def test_limit_order_with_price(self):
        args = make_order_place_args(
            symbol="C-BTC-95000-310726",
            side="SELL",
            order_type="LIMIT",
            quantity=50,
            price=3300,
        )
        assert args["order_type"] == "limit_order"
        assert args["limit_price"] == "3300"

    def test_stop_order_with_trigger(self):
        args = make_order_place_args(
            symbol="P-BTC-95000-310726",
            side="BUY",
            order_type="STOP_MARKET",
            quantity=100,
            trigger_price=16000,
        )
        assert args["order_type"] == "stop_order"
        assert args["stop_price"] == "16000"

    def test_order_with_tag(self):
        args = make_order_place_args(
            symbol="C-BTC-95000-310726",
            side="BUY",
            quantity=100,
            tag="my_btc_trade",
        )
        assert args["client_oid"] == "my_btc_trade"

    def test_mis_product_type(self):
        args = make_order_place_args(
            symbol="C-BTC-95000-310726",
            side="BUY",
            quantity=100,
            product_type="MIS",
        )
        assert args["product_type"] == "intrady"


class TestMakeOrderModifyArgs:
    def test_minimal_modify(self):
        args = make_order_modify_args(order_id="ord_001")
        assert args["order_id"] == "ord_001"

    def test_modify_quantity(self):
        args = make_order_modify_args(order_id="ord_001", quantity=200)
        assert args["size"] == "200"

    def test_modify_price(self):
        args = make_order_modify_args(order_id="ord_001", price=3400)
        assert args["limit_price"] == "3400"

    def test_modify_trigger_price(self):
        args = make_order_modify_args(order_id="ord_001", trigger_price=15500)
        assert args["stop_price"] == "15500"

    def test_modify_order_type(self):
        args = make_order_modify_args(order_id="ord_001", order_type="LIMIT")
        assert args["order_type"] == "limit_order"


class TestPostOrderHook:
    def test_empty_returns_empty_list(self):
        assert post_order_hook() == []

    def test_single_order_standardizes(self):
        raw = [{
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
        }]
        result = post_order_hook(*raw)
        assert len(result) == 1
        assert result[0]["order_id"] == "ord_001"
        assert result[0]["symbol"] == "C-BTC-95000-310726"
        assert result[0]["side"] == "BUY"
        assert result[0]["order_type"] == "LIMIT"
        assert result[0]["status"] == "OPEN"

    def test_nested_list_flattens(self):
        raw = [[{
            "id": "ord_001",
            "symbol": "C-BTC-95000-310726",
            "side": "buy",
            "size": "100",
            "state": "open",
        }]]
        result = post_order_hook(*raw)
        assert len(result) == 1


class TestPostTradeHook:
    def test_empty_returns_empty_list(self):
        assert post_trade_hook() == []

    def test_single_trade_standardizes(self):
        raw = [{
            "id": "trd_001",
            "order_id": "ord_001",
            "symbol": "C-BTC-95000-310726",
            "side": "buy",
            "size": "100",
            "price": "3150",
            "timestamp": "2026-05-13T10:00:00Z",
        }]
        result = post_trade_hook(*raw)
        assert len(result) == 1
        assert result[0]["trade_id"] == "trd_001"
        assert result[0]["order_id"] == "ord_001"
        assert result[0]["symbol"] == "C-BTC-95000-310726"
        assert result[0]["fill_price"] == "3150"
