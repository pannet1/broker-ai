from stock_brokers.flattrade.api_helper import (
    ShoonyaApiPy,
    make_order_place_args,
    make_order_modify_args,
    post_order_hook,
    post_trade_hook,
)
from stock_brokers.flattrade.session import get_session_token
from stock_brokers.base import Broker, pre, post
from typing import List, Dict, Union
from traceback import print_exc


class Flattrade(Broker):
    """
    Automated Trading class
    """

    def __init__(
        self,
        user_id: str,
        password: str,
        pin: str,
        vendor_code: str,
        app_key: str,
        imei: str,
        api_secret: str,
        broker: str = "",
    ):
        self._user_id = user_id
        self._password = password
        self._pin = pin
        self._vendor_code = vendor_code
        self._app_key = app_key
        self._api_secret = api_secret
        self._imei = imei
        self.broker = ShoonyaApiPy(
            host="https://piconnect.flattrade.in/PiConnectAPI/",
            websocket="wss://piconnect.flattrade.in/PiConnectWSAPI/",
        )
        super(Flattrade, self).__init__()

    def authenticate(self) -> Union[Dict, None]:
        try:
            self._user_token = get_session_token(
                userid=self._user_id,
                password=self._password,
                twoFA=self._pin,
                api_key=self._app_key,
                api_secret=self._api_secret,
                verbose=True,
            )
            return self.broker.set_session(
                userid=self._user_id,
                password=self._password,
                usertoken=self._user_token,
            )  # type: ignore
        except Exception as e:
            print(f"{e} in login")
            print_exc()
            return None

    @property
    @post
    def orders(self) -> List[Dict]:
        try:
            orderbook = self.broker.get_order_book()
            if not orderbook or len(orderbook) == 0:
                return [{}]
            # return post_order_hook(*orderbook)
            return orderbook
        except Exception as e:
            print(f"{e} in stock broker order book")
            print_exc()
            return [{}]

    @property
    @post
    def trades(self) -> List[Dict]:
        try:
            tradebook = self.broker.get_trade_book()
            if not tradebook or len(tradebook) == 0:
                return []
            # return post_trade_hook(*tradebook)
            return tradebook
        except Exception as e:
            print(f"{e} in stock broker trade book")
            print_exc()
            return [{}]

    @property
    @post
    def positions(self) -> List[Dict]:
        positionbook = self.broker.get_positions()

        if not positionbook or len(positionbook) == 0:
            return [{}]

        position_list = []
        int_cols = [
            "netqty",
            "daybuyqty",
            "daysellqty",
            "cfbuyqty",
            "cfsellqty",
            "openbuyqty",
            "opensellqty",
        ]
        float_cols = [
            "daybuyamt",
            "daysellamt",
            "lp",
            "rpnl",
            "dayavgprc",
            "daybuyavgprc",
            "daysellavgprc",
            "urmtom",
        ]
        for position in positionbook:
            try:
                for int_col in int_cols:
                    position[int_col] = int(position.get(int_col, 0))
                for float_col in float_cols:
                    position[float_col] = float(position.get(float_col, 0))
            except Exception as e:
                print(f"{e} while iter stockbroker positions")
                print_exc()
            position_list.append(position)
        return position_list

    @pre
    def order_place(self, **kwargs) -> Union[str, None]:
        try:
            print(f"before making args {kwargs}")
            margs = make_order_place_args(**kwargs)
            print(f"after making args {margs}")
            response = self.broker.place_order(**margs)
            if isinstance(response, dict) and response.get("norenordno") is not None:
                return response["norenordno"]
        except Exception as err:
            print(f"{err} in stock_brokers order_place with {kwargs}")
            print_exc()

    @post
    def order_cancel(self, order_id: str) -> Union[Dict, None]:
        """
        Cancel an existing order
        """
        return self.broker.cancel_order(orderno=order_id)

    @pre
    def order_modify(self, **kwargs) -> Union[str, None]:
        """
        Modify an existing order
        """
        try:
            print(f"before modify args {kwargs}")
            margs = make_order_modify_args(**kwargs)
            print(f"after modify args {margs}")
            response = self.broker.modify_order(**margs)
            if response is not None:
                return response
            else:
                raise Exception("stock broker got no response for")
        except Exception as e:
            print(f"{e} order modify with params {kwargs}")
            print_exc()

    @property
    def margins(self):
        return self.broker.get_limits()

    def instrument_symbol(self, exch: str, txt: str):
        res = self.broker.searchscrip(exchange=exch, searchtext=txt)
        if res:
            return res["values"][0].get("token", 0)

    def historical(self, exch: str, tkn: str, fm: str, to: str, tf: int = 1):
        """
        ret = api.get_time_price_series(exchange='NSE', token='22',
        starttime=obj_datetime.timestamp(), interval=5)
        interval: acceptable integer values in minutes are
        “1”, ”3”, “5”, “10”, “15”, “30”, “60”, “120”, “240”
        """
        return self.broker.get_time_price_series(exch, tkn, fm, to, tf)

    def scriptinfo(self, exch: str, tkn: str):
        return self.broker.get_security_info(exch, tkn)
