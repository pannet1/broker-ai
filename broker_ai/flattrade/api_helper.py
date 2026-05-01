from stock_brokers.flattrade.NorenApi import NorenApi
import time
import concurrent.futures
import pendulum
from traceback import print_exc
from typing import List, Dict


def convert_time_string(dct, key, fmt):
    # pendulum current datetime
    try:
        if dct.get(key, None) is None:
            ts = pendulum.now(tz="Asia/Kolkata").format("DD-MM-YYYY HH:mm:ss")
        else:
            ts = dct.pop(key)
        dct[key] = str(pendulum.from_format(ts, fmt=fmt, tz="Asia/Kolkata"))
    except Exception as e:
        print(f"{e} while converting time to string for {key=} and {fmt=}")
    finally:
        return dct


def filter_dictionary_by_keys(elephant: Dict, keys: List) -> Dict:
    """
    generic function to filter any dict
    """
    if not any(elephant):
        return elephant

    filtered = {}
    for item in keys:
        filtered[item] = elephant.get(item, None)
    return filtered


def get_order_type(order_type: str) -> str:
    order_types = {
        "LIMIT": "LMT",
        "MARKET": "MKT",
        "SL": "SL-LMT",
        "SLL": "SL-LMT",
        "SL-L": "SL-LMT",
        "SLM": "SL-MKT",
        "SL-M": "SL-MKT",
    }
    return order_types.get(order_type.upper(), order_type)


def get_product(product_type: str) -> str:
    product_types = {"MIS": "I", "CNC": "C", "NRML": "M", "BRACKET": "B", "COVER": "H"}
    return product_types.get(product_type.upper(), product_type)


def make_order_modify_args(**kwargs) -> Dict:
    order_args = dict(
        orderno=kwargs.pop("orderno"),
        tradingsymbol=convert_symbol(
            kwargs.pop("tradingsymbol", None), kwargs["exchange"]
        ),
        exchange=kwargs.pop("exchange"),
        newprice_type=get_order_type(kwargs.pop("newprice_type")),
        newprice=(lambda x: x if x >= 0 else 0.05)(kwargs.pop("newprice", 0)),
        newquantity=kwargs.pop("newquantity"),
    )
    if kwargs.get("newtrigger_price", None):
        order_args["newtrigger_price"] = kwargs.pop("newtrigger_price")
    print(f"remaining dictionary items: {kwargs}")
    return order_args


def make_order_place_args(**kwargs) -> Dict:
    order_args = dict(
        buy_or_sell=kwargs.pop("buy_or_sell")[0].upper(),
        product_type=get_product(kwargs.pop("product_type", "I")),
        tradingsymbol=convert_symbol(
            kwargs.pop("tradingsymbol", None), kwargs["exchange"]
        ),
        discloseqty=kwargs.pop("discloseqty", kwargs["quantity"]),
        price_type=get_order_type(kwargs.pop("price_type")),
        retention=kwargs.pop("retention", "DAY"),
        quantity=kwargs["quantity"],
        exchange=kwargs["exchange"],
        remarks=kwargs.pop("remarks", "stock_brokers"),
    )
    if kwargs.get("trigger_price", None):
        order_args["trigger_price"] = kwargs.pop("trigger_price")
    if kwargs.get("price", None):
        order_args["price"] = kwargs.pop("price")
    print(f"remaing dict {kwargs}")
    return order_args


def post_trade_hook(*tradebook):
    try:
        trade_list = []
        keys = [
            "exchange",
            "symbol",
            "order_id",
            "quantity",
            "side",
            "product",
            "price_type",
            "fill_shares",
            "average_price",
            "exchange_order_id",
            "tag",
            "validity",
            "price_precison",
            "tick_size",
            "fill_timestamp",
            "fill_quantity",
            "fill_price",
            "source",
            "broker_timestamp",
        ]
        if tradebook and any(tradebook):
            tradebook = [filter_dictionary_by_keys(trade, keys) for trade in tradebook]
            int_cols = ["flqty", "qty", "fillshares"]
            float_cols = ["prc", "flprc"]
            for trade in tradebook:
                try:
                    for int_col in int_cols:
                        trade[int_col] = int(trade.get(int_col, 0))
                    for float_col in float_cols:
                        trade[float_col] = float(trade.get(float_col, 0))
                    now = pendulum.now(tz="Asia/Kolkata").format("DD-MM-YYYY HH:mm:ss")
                    ts = trade.get("norentm", now)
                    """
                    trade["broker_timestamp"] = str(
                        pendulum.from_format(
                            ts, fmt="HH:mm:ss DD-MM-YYYY", tz="Asia/Kolkata"
                        )
                    )
                    """
                    trade_list.append(trade)
                except Exception as e:
                    print(f"{e} while iter stockbroker trades")
                    print_exc()
        return trade_list
    except Exception as e:
        print(f"{e} while processing stock_brokers tradebook")
        print_exc()


def post_order_hook(*orderbook):
    try:
        keys = [
            "tsym",
            "norenordno",
            "qty",
            "prc",
            "trantype",
            "filled_quantity",
            "exchange",
            "exchange_order_id",
            "disclosed_quantity",
            "broker_timestamp",
            "exchange_timestamp",
            "status",
            "product",
            "order_type",
        ]
        # Extract only the key-value pairs where the key is in the predefined keys list
        orderbook = [filter_dictionary_by_keys(order, keys) for order in orderbook]
        # Copy broker fields to standard names
        for order in orderbook:
            if order.get("tsym"):
                order["symbol"] = order.get("tsym")
            if order.get("norenordno"):
                order["order_id"] = order.get("norenordno")
            if order.get("qty"):
                order["quantity"] = order.get("qty")
            if order.get("prc"):
                order["price"] = order.get("prc")
            if order.get("trantype"):
                order["side"] = order.get("trantype")
            if order.get("fillshares"):
                order["filled_quantity"] = order.get("fillshares")
        float_cols = ["average_price", "price", "trigger_price"]
        int_cols = ["filled_quantity", "quantity"]
        order_list = []
        for order in orderbook:
            print(order)
            for int_col in int_cols:
                order[int_col] = (
                    lambda x: int(x) if isinstance(x, str) and x.replace(".", "").isdigit() else 0
                )(order.get(int_col, 0))
            for float_col in float_cols:
                order[float_col] = (
                    lambda x: float(x) if isinstance(x, str) and x.replace(".", "").isdigit() else 0.0
                )(order.get(float_col, 0.0))

            order = convert_time_string(
                order, "exchange_timestamp", "DD-MM-YYYY HH:mm:ss"
            )
            """
            order = convert_time_string(
                order, "broker_timestamp", "HH:mm:ss DD-MM-YYYY"
            )
            """
            order_list.append(order)
        return order_list
    except Exception as e:
        print(f"{e} while processing stock_brokers orderbook")
        print_exc()


def convert_symbol(symbol: str, exchange: str = "NSE") -> str:
    """
    Convert raw symbol to finvasia
    """
    if exchange == "NSE":
        if symbol.endswith("-EQ"):
            return symbol
        elif symbol.endswith("-eq"):
            return symbol.upper()
        else:
            return f"{symbol}-EQ"
    return symbol


api = None


class Order:
    def __init__(
        self,
        buy_or_sell: str = "BUY",
        product_type: str = None,
        exchange: str = None,
        tradingsymbol: str = None,
        price_type: str = None,
        quantity: int = None,
        price: float = None,
        trigger_price: float = None,
        discloseqty: int = 0,
        retention: str = "DAY",
        remarks: str = "tag",
        order_id=None,
    ):
        self.buy_or_sell = buy_or_sell
        self.product_type = product_type
        self.exchange = exchange
        self.tradingsymbol = tradingsymbol
        self.quantity = quantity
        self.discloseqty = discloseqty
        self.price_type = price_type
        self.price = price
        self.trigger_price = trigger_price
        self.retention = retention
        self.remarks = remarks
        self.order_id = None


# print(ret)


def get_time(time_string):
    data = time.strptime(time_string, "%d-%m-%Y %H:%M:%S")

    return time.mktime(data)


class ShoonyaApiPy(NorenApi):
    def __init__(self, host, websocket):
        NorenApi.__init__(self, host=host, websocket=websocket)
        global api
        api = self

    def place_basket(self, orders):

        resp_err = 0
        resp_ok = 0
        result = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {
                executor.submit(self.place_order, order): order for order in orders
            }
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
            try:
                result.append(future.result())
            except Exception as exc:
                print(exc)
                resp_err = resp_err + 1
            else:
                resp_ok = resp_ok + 1

        return result

    def placeOrder(self, order: Order):
        ret = NorenApi.place_order(
            self,
            buy_or_sell=order.buy_or_sell,
            product_type=order.product_type,
            exchange=order.exchange,
            tradingsymbol=order.tradingsymbol,
            quantity=order.quantity,
            discloseqty=order.discloseqty,
            price_type=order.price_type,
            price=order.price,
            trigger_price=order.trigger_price,
            retention=order.retention,
            remarks=order.remarks,
        )
        # print(ret)

        return ret
