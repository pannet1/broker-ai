import pendulum
from typing import Optional
from broker_ai.delta.api_helper import (
    DeltaAPI,
    make_order_place_args,
    make_order_modify_args,
    post_order_hook,
    post_trade_hook,
)
from broker_ai.base import Broker, pre, post
from typing import List, Dict, Union
from traceback import print_exc


class Delta(Broker):
    """
    Delta Exchange Automated Trading class
    Similar to Flattrade and Zerodha implementations
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        broker: str = "",
    ):
        self._api_key = api_key
        self._api_secret = api_secret
        self.broker = DeltaAPI(api_key=api_key, api_secret=api_secret)
        super(Delta, self).__init__()

    def authenticate(self) -> Union[Dict, None]:
        """
        Authenticate with Delta Exchange
        Tests the API credentials by fetching products
        """
        try:
            products = self.broker.get_products()
            if products:
                print(f"Successfully authenticated with Delta Exchange")
                print(f"Found {len(products) if isinstance(products, list) else 'multiple'} products")
                return {"status": "authenticated", "products_count": len(products) if isinstance(products, list) else 0}
            else:
                print("Authentication failed - no products returned")
                return None
        except Exception as e:
            print(f"{e} in login")
            print_exc()
            return None

    @property
    @post
    def orders(self) -> List[Dict]:
        """Get all orders"""
        try:
            orderbook = self.broker.get_active_orders()
            if not orderbook or len(orderbook) == 0:
                return [{}]
            return post_order_hook(*orderbook)
        except Exception as e:
            print(f"{e} in delta order book")
            print_exc()
            return [{}]

    @property
    @post
    def trades(self) -> List[Dict]:
        """Get all trades"""
        try:
            tradebook = self.broker.get_fills()
            if not tradebook or len(tradebook) == 0:
                return []
            return post_trade_hook(*tradebook)
        except Exception as e:
            print(f"{e} in delta trade book")
            print_exc()
            return []

    @property
    @post
    def positions(self) -> List[Dict]:
        """Get all positions"""
        try:
            positionbook = self.broker.get_positions()
            
            if not positionbook or len(positionbook) == 0:
                return [{}]
            
            position_list = []
            for position in positionbook:
                try:
                    std_position = {
                        "symbol": position.get("symbol"),
                        "product_id": position.get("product_id"),
                        "quantity": float(position.get("quantity", 0)),
                        "side": position.get("side", "").upper(),
                        "average_price": float(position.get("average_price", 0)),
                        "mark_price": float(position.get("mark_price", 0)),
                        "unrealized_pnl": float(position.get("unrealized_pnl", 0)),
                        "realized_pnl": float(position.get("realized_pnl", 0)),
                        "leverage": position.get("leverage", 1),
                        "margin": float(position.get("margin", 0)),
                        "liquidation_price": position.get("liquidation_price"),
                    }
                    position_list.append(std_position)
                except Exception as e:
                    print(f"{e} while processing position")
                    print_exc()
            
            return position_list
        except Exception as e:
            print(f"{e} in delta positions")
            print_exc()
            return [{}]

    @pre
    def order_place(self, **kwargs) -> Union[str, None]:
        """
        Place an order
        
        Args:
            symbol: Product symbol (e.g., BTCUSD)
            side: BUY or SELL
            order_type: LIMIT, MARKET, STOP_LIMIT, STOP_MARKET
            quantity: Order quantity
            product_type: MIS, CNC, NRML
            price: Limit price (for limit orders)
            trigger_price: Stop price (for stop orders)
            tag: Client order ID
        """
        try:
            print(f"before making args {kwargs}")
            margs = make_order_place_args(**kwargs)
            print(f"after making args {margs}")
            response = self.broker.place_order(**margs)
            
            if response and isinstance(response, dict):
                order_id = response.get("id") or response.get("client_oid")
                if order_id:
                    return order_id
                return response
            return None
        except Exception as err:
            print(f"{err} in delta order_place with {kwargs}")
            print_exc()
            return None

    @post
    def order_cancel(self, order_id: str) -> Union[Dict, None]:
        """
        Cancel an existing order
        
        Args:
            order_id: Order ID to cancel
        """
        try:
            response = self.broker.cancel_order(order_id=order_id)
            if response:
                return response
            return None
        except Exception as e:
            print(f"{e} in order_cancel with order_id={order_id}")
            print_exc()
            return None

    @pre
    def order_modify(self, **kwargs) -> Union[Dict, None]:
        """
        Modify an existing order
        
        Args:
            order_id: Order ID to modify
            quantity: New quantity
            price: New limit price
            order_type: New order type
            trigger_price: New stop price
        """
        try:
            print(f"before modify args {kwargs}")
            margs = make_order_modify_args(**kwargs)
            print(f"after modify args {margs}")
            response = self.broker.edit_order(**margs)
            
            if response:
                return response
            else:
                raise Exception("Delta got no response for order modify")
        except Exception as e:
            print(f"{e} order modify with params {kwargs}")
            print_exc()
            return None

    @property
    def margins(self) -> Dict:
        """Get wallet balances/margins"""
        try:
            balances = self.broker.get_wallet_balances()
            if balances:
                return {"balances": balances}
            return {}
        except Exception as e:
            print(f"{e} in margins")
            print_exc()
            return {}

    @property
    def profile(self) -> Dict:
        """Get user profile"""
        try:
            return self.broker._request("GET", "/v2/user")
        except Exception as e:
            print(f"{e} in profile")
            print_exc()
            return {}

    def instrument_symbol(self, symbol: str) -> Union[Dict, None]:
        """Get product details by symbol"""
        try:
            product = self.broker.get_product(symbol=symbol)
            if product:
                return product
            return None
        except Exception as e:
            print(f"{e} in instrument_symbol for {symbol}")
            print_exc()
            return None

    def get_products(self, contract_types: Optional[str] = None) -> List[Dict]:
        """Get list of all products"""
        try:
            if contract_types:
                return self.broker.get_tickers(contract_types=contract_types)
            return self.broker.get_products()
        except Exception as e:
            print(f"{e} in get_products")
            print_exc()
            return []

    def historical(
        self,
        symbol: str,
        resolution: str = "1",
        from_time: Union[str, int, pendulum.DateTime, None] = None,
        to_time: Union[str, int, pendulum.DateTime, None] = None,
        tz: str = "Asia/Kolkata",
    ) -> List[Dict]:
        """
        Get historical OHLC candles
        
        Args:
            symbol: Product symbol (e.g., BTCUSD)
            resolution: Candle interval (1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M)
            from_time: Start time - accepts pendulum.DateTime, string, or int timestamp
            to_time: End time - accepts pendulum.DateTime, string, or int timestamp
            tz: Timezone for string parsing (default: Asia/Kolkata)
        
        Returns:
            List of candle data with keys: time, open, high, low, close, volume
        
        Example:
            # Using pendulum
            from_time = pendulum.now(tz="Asia/Kolkata").subtract(days=7)
            to_time = pendulum.now(tz="Asia/Kolkata")
            delta.historical("BTCUSD", resolution="5", from_time=from_time, to_time=to_time)
            
            # Using string
            delta.historical("BTCUSD", resolution="15", from_time="2024-01-01", to_time="2024-01-02")
            
            # Using timestamp
            delta.historical("BTCUSD", resolution="60", from_time=1609459200, to_time=1609545600)
        """
        try:
            start_ts = self._convert_to_timestamp(from_time, tz) if from_time else None
            end_ts = self._convert_to_timestamp(to_time, tz) if to_time else None
            
            candles = self.broker.get_historical_candles(
                symbol=symbol,
                resolution=resolution,
                start=start_ts,
                end=end_ts,
            )
            
            if candles:
                standardized = []
                for candle in candles:
                    std_candle = {
                        "time": candle.get("time"),
                        "open": float(candle.get("open", 0)),
                        "high": float(candle.get("high", 0)),
                        "low": float(candle.get("low", 0)),
                        "close": float(candle.get("close", 0)),
                        "volume": float(candle.get("volume", 0)),
                    }
                    standardized.append(std_candle)
                return standardized
            
            return []
        except Exception as e:
            print(f"{e} in historical for {symbol}")
            print_exc()
            return []
    
    def _convert_to_timestamp(
        self,
        time_input: Union[str, int, pendulum.DateTime],
        tz: str = "Asia/Kolkata",
    ) -> int:
        """
        Convert various time formats to Unix timestamp using pendulum
        
        Args:
            time_input: pendulum.DateTime, string, or int timestamp
            tz: Timezone for string parsing
        
        Returns:
            Unix timestamp in seconds
        """
        try:
            if isinstance(time_input, pendulum.DateTime):
                return int(time_input.timestamp())
            elif isinstance(time_input, int):
                return time_input
            elif isinstance(time_input, str):
                dt = pendulum.from_format(time_input, "YYYY-MM-DD HH:mm:ss", tz=tz)
                return int(dt.timestamp())
            else:
                print(f"Unsupported time format: {type(time_input)}")
                return None
        except Exception as e:
            print(f"{e} while converting time to timestamp")
            print_exc()
            return None

    def ltp(self, symbol: str) -> Dict:
        """Get last traded price for a symbol"""
        try:
            ticker = self.broker.get_ticker(symbol=symbol)
            if ticker:
                return {
                    "symbol": symbol,
                    "ltp": float(ticker.get("last_price", 0)),
                    "change": ticker.get("change_24h"),
                    "volume": ticker.get("volume_24h"),
                }
            return {}
        except Exception as e:
            print(f"{e} in ltp for {symbol}")
            print_exc()
            return {}

    def orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """Get orderbook for a symbol"""
        try:
            return self.broker.get_orderbook(symbol=symbol, limit=limit)
        except Exception as e:
            print(f"{e} in orderbook for {symbol}")
            print_exc()
            return {}
