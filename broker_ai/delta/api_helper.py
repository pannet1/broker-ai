import hashlib
import hmac
import time
import requests
from typing import Dict, Optional, Union
from traceback import print_exc


BASE_URL = "https://api.india.delta.exchange"


def generate_signature(secret: str, message: str) -> str:
    """Generate HMAC SHA256 signature"""
    message = bytes(message, 'utf-8')
    secret = bytes(secret, 'utf-8')
    hash_obj = hmac.new(secret, message, hashlib.sha256)
    return hash_obj.hexdigest()


def non_shrinking(fetch_fn):
    cache = []
    def wrapper(*args, **kwargs):
        nonlocal cache
        result = fetch_fn(*args, **kwargs)
        if isinstance(result, list) and len(result) >= len(cache):
            cache[:] = result
        return list(cache)
    return wrapper


def get_side(side: str) -> str:
    """Convert side to Delta format"""
    side_map = {
        "BUY": "buy",
        "SELL": "sell",
        "buy": "buy",
        "sell": "sell"
    }
    return side_map.get(side.upper(), side.lower())


def get_order_type(order_type: str) -> str:
    """Convert order type to Delta format"""
    order_type_map = {
        "LIMIT": "limit_order",
        "MARKET": "market_order",
        "STOP_LIMIT": "stop_order",
        "STOP_MARKET": "stop_order",
        "SL": "stop_order",
        "SLM": "stop_order",
    }
    return order_type_map.get(order_type.upper(), "limit_order")


def get_product_type(product_type: str) -> str:
    """Convert product type to Delta format"""
    product_map = {
        "MIS": "intrady",
        "CNC": "delivery",
        "NRML": "carryforward",
        "CO": "cover",
        "BO": "bracket",
    }
    return product_map.get(product_type.upper(), "carryforward")


def make_order_place_args(**kwargs) -> Dict:
    """Convert standard order args to Delta format"""
    order_args = dict(
        symbol=kwargs.pop("symbol"),
        side=get_side(kwargs.pop("side")),
        order_type=get_order_type(kwargs.pop("order_type", "MARKET")),
        size=str(kwargs.pop("quantity")),
        product_type=get_product_type(kwargs.pop("product_type", "NRML")),
    )
    
    if kwargs.get("price", None):
        order_args["limit_price"] = str(kwargs.pop("price"))
    
    if kwargs.get("trigger_price", None):
        order_args["stop_price"] = str(kwargs.pop("trigger_price"))
    
    if kwargs.get("tag", None):
        order_args["client_oid"] = kwargs.pop("tag")
    
    print(f"Delta order place args: {order_args}")
    return order_args


def make_order_modify_args(**kwargs) -> Dict:
    """Convert standard modify args to Delta format"""
    order_args = dict(
        order_id=kwargs.pop("order_id"),
    )
    
    if kwargs.get("quantity", None):
        order_args["size"] = str(kwargs["quantity"])
    
    if kwargs.get("price", None):
        order_args["limit_price"] = str(kwargs["price"])
    
    if kwargs.get("order_type", None):
        order_args["order_type"] = get_order_type(kwargs["order_type"])
    
    if kwargs.get("trigger_price", None):
        order_args["stop_price"] = str(kwargs["trigger_price"])
    
    print(f"Delta order modify args: {order_args}")
    return order_args


def post_order_hook(*orderbook) -> list:
    """Transform Delta order response to standard format"""
    try:
        if not orderbook or len(orderbook) == 0:
            return []
        
        order_list = []
        for order in orderbook:
            if isinstance(order, list):
                order_list.extend(order)
            else:
                order_list.append(order)
        
        standardized = []
        for order in order_list:
            std_order = {
                "order_id": order.get("id", order.get("client_oid")),
                "symbol": order.get("symbol"),
                "side": order.get("side", "").upper(),
                "quantity": order.get("size", order.get("quantity")),
                "price": order.get("limit_price", order.get("price")),
                "order_type": order.get("order_type", "").replace("_order", "").upper(),
                "status": order.get("state", order.get("status", "")).upper(),
                "filled_quantity": order.get("filled_size", order.get("filled_quantity", 0)),
                "average_price": order.get("average_price", 0),
                "product_type": order.get("product_type"),
                "created_at": order.get("created_at"),
                "updated_at": order.get("updated_at"),
            }
            standardized.append(std_order)
        
        return standardized
    except Exception as e:
        print(f"{e} in post_order_hook")
        print_exc()
        return []


def post_trade_hook(*tradebook) -> list:
    """Transform Delta trade response to standard format"""
    try:
        if not tradebook or len(tradebook) == 0:
            return []
        
        trade_list = []
        for trade in tradebook:
            if isinstance(trade, list):
                trade_list.extend(trade)
            else:
                trade_list.append(trade)
        
        standardized = []
        for trade in trade_list:
            std_trade = {
                "trade_id": trade.get("id"),
                "order_id": trade.get("order_id"),
                "symbol": trade.get("symbol"),
                "side": trade.get("side", "").upper(),
                "quantity": trade.get("size", trade.get("quantity")),
                "price": trade.get("price"),
                "fill_price": trade.get("price"),
                "fill_quantity": trade.get("size", trade.get("quantity")),
                "created_at": trade.get("timestamp", trade.get("created_at")),
            }
            standardized.append(std_trade)
        
        return standardized
    except Exception as e:
        print(f"{e} in post_trade_hook")
        print_exc()
        return []


class DeltaAPI:
    """Delta Exchange REST API client"""
    
    def __init__(self, api_key: str, api_secret: str, base_url: str = BASE_URL):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.session = requests.Session()
    
    def _generate_signature(self, method: str, path: str, query_string: str = "", payload: str = "") -> str:
        """Generate signature for authentication"""
        timestamp = str(int(time.time()))
        signature_data = method + timestamp + path + query_string + payload
        return generate_signature(self.api_secret, signature_data), timestamp
    
    def _request(self, method: str, path: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Union[Dict, list]:
        """Make authenticated request to Delta API"""
        try:
            query_string = ""
            payload = ""
            
            if params:
                query_string = "?" + "&".join([f"{k}={v}" for k, v in params.items()])
            
            if data:
                payload = requests.compat.json.dumps(data)
            
            signature, timestamp = self._generate_signature(method, path, query_string, payload)
            
            headers = {
                'api-key': self.api_key,
                'timestamp': timestamp,
                'signature': signature,
                'User-Agent': 'python-3.10',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}{path}{query_string}"
            
            response = self.session.request(
                method,
                url,
                json=data if data else None,
                params=params if params else None,
                headers=headers,
                timeout=(3, 27)
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("success"):
                return result.get("result", {})
            else:
                print(f"API Error: {result.get('error', {})}")
                return {}
                
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            print_exc()
            return {}
        except Exception as e:
            print(f"Error in _request: {e}")
            print_exc()
            return {}
    
    def get_products(self) -> list:
        """Get list of all products"""
        return self._request("GET", "/v2/products")
    
    def get_product(self, symbol: str) -> Dict:
        """Get product by symbol"""
        return self._request("GET", f"/v2/products/{symbol}")
    
    def get_ticker(self, symbol: str) -> Dict:
        """Get ticker for a product"""
        return self._request("GET", f"/v2/tickers/{symbol}")
    
    def get_tickers(self, contract_types: Optional[str] = None) -> list:
        """Get tickers for products"""
        params = {}
        if contract_types:
            params["contract_types"] = contract_types
        return self._request("GET", "/v2/tickers", params=params)
    
    def get_active_orders(self, product_id: Optional[int] = None, state: str = "open") -> list:
        """Get active orders"""
        params = {"state": state}
        if product_id:
            params["product_id"] = product_id
        return self._request("GET", "/v2/orders", params=params)
    
    def get_order_history(self, product_id: Optional[int] = None, start_time: Optional[int] = None, end_time: Optional[int] = None) -> list:
        """Get order history"""
        params = {}
        if product_id:
            params["product_id"] = product_id
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        return self._request("GET", "/v2/orders/history", params=params)
    
    def place_order(self, **kwargs) -> Dict:
        """Place an order"""
        return self._request("POST", "/v2/orders", data=kwargs)
    
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order"""
        data = {"order_id": order_id}
        return self._request("DELETE", "/v2/orders", data=data)
    
    def edit_order(self, order_id: str, **kwargs) -> Dict:
        """Edit an order"""
        kwargs["order_id"] = order_id
        return self._request("PUT", "/v2/orders", data=kwargs)
    
    def get_positions(self) -> list:
        """Get positions"""
        return self._request("GET", "/v2/positions")
    
    def get_position(self, product_id: int) -> Dict:
        """Get specific position"""
        return self._request("GET", f"/v2/positions/{product_id}")
    
    def get_wallet_balances(self) -> list:
        """Get wallet balances"""
        return self._request("GET", "/v2/wallet/balances")
    
    def get_fills(self, product_id: Optional[int] = None, start_time: Optional[int] = None, end_time: Optional[int] = None) -> list:
        """Get trade fills"""
        params = {}
        if product_id:
            params["product_id"] = product_id
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        return self._request("GET", "/v2/fills", params=params)
    
    def get_historical_candles(
        self,
        symbol: str,
        resolution: str = "1",
        start: Optional[int] = None,
        end: Optional[int] = None
    ) -> list:
        """
        Get historical OHLC candles
        
        Args:
            symbol: Product symbol (e.g., BTCUSD)
            resolution: Candle interval (1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M)
            start: Start timestamp in seconds
            end: End timestamp in seconds
        """
        params = {
            "symbol": symbol,
            "resolution": resolution,
        }
        
        if start:
            params["from"] = start
        if end:
            params["to"] = end
        
        return self._request("GET", "/v2/historical_candles", params=params)
    
    def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """Get L2 orderbook"""
        params = {"symbol": symbol, "limit": limit}
        return self._request("GET", "/v2/orderbook", params=params)
