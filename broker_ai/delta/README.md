# Delta Exchange Integration

Complete Delta Exchange India integration similar to Flattrade and Zerodha implementations.

## Features

✅ **Authentication** - API key/secret based authentication with HMAC signing
✅ **Order Management** - Place, modify, cancel orders with pre-hooks
✅ **Order Book** - Get active orders with post-hooks for response transformation
✅ **Trade Book** - Get filled trades with post-hooks
✅ **Positions** - Get current positions with P&L
✅ **Historical API** - Get OHLC candle data
✅ **Pre/Post Hooks** - Automatic field mapping and transformation
✅ **Override Support** - YAML-based field mapping configuration

## Files Created

```
broker_ai/delta/
├── __init__.py          # Package exports
├── api_helper.py        # REST API client with authentication
├── delta.py             # Main Delta broker class
├── delta.yaml           # Field mapping overrides
└── README.md            # This file

examples/
└── delta_example.py     # Usage examples
```

## Setup

### 1. Get API Credentials

1. Visit https://www.delta.exchange/app/account/manageapikeys
2. Create new API key with:
   - **Trading** permission (for orders)
   - **Read Data** permission (for market data)
   - **IP Whitelist** (your server IP)

### 2. Installation

The integration is part of the `broker-ai` package. No additional dependencies needed beyond `requests`.

### 3. Usage

```python
from broker_ai.delta import Delta

# Initialize
delta = Delta(
    api_key="your_api_key",
    api_secret="your_api_secret"
)

# Authenticate
delta.authenticate()

# Place order
order_id = delta.order_place(
    symbol="BTCUSD",
    side="BUY",
    order_type="LIMIT",
    quantity=100,
    price=50000,
    product_type="NRML",
    tag="my_order_1"
)

# Get orders
orders = delta.orders

# Get positions
positions = delta.positions

# Get trades
trades = delta.trades

# Cancel order
delta.order_cancel(order_id=order_id)

# Modify order
delta.order_modify(
    order_id=order_id,
    price=51000,
    quantity=150
)

# Get historical data (5-minute candles for last 24 hours)
import time
end_time = int(time.time())
start_time = end_time - (3600 * 24)

candles = delta.historical(
    symbol="BTCUSD",
    resolution="5",
    start=start_time,
    end=end_time,
)

# Get margins
margins = delta.margins

# Get LTP
ltp = delta.ltp("BTCUSD")

# Get products
products = delta.get_products()
```

## API Reference

### Authentication

```python
delta.authenticate()
```
Tests API credentials and returns authentication status.

### Order Placement

```python
delta.order_place(
    symbol: str,           # Product symbol (e.g., BTCUSD)
    side: str,             # BUY or SELL
    order_type: str,       # LIMIT, MARKET, STOP_LIMIT, STOP_MARKET
    quantity: int,         # Order quantity
    product_type: str,     # MIS, CNC, NRML
    price: float = None,   # Limit price
    trigger_price: float = None,  # Stop price
    tag: str = None        # Client order ID
) -> str
```

### Order Modification

```python
delta.order_modify(
    order_id: str,         # Order ID to modify
    quantity: int = None,  # New quantity
    price: float = None,   # New limit price
    order_type: str = None,  # New order type
    trigger_price: float = None  # New stop price
) -> Dict
```

### Order Cancellation

```python
delta.order_cancel(order_id: str) -> Dict
```

### Get Orders

```python
delta.orders -> List[Dict]
```

### Get Positions

```python
delta.positions -> List[Dict]
```

Returns positions with fields:
- symbol, product_id, quantity, side
- average_price, mark_price
- unrealized_pnl, realized_pnl
- leverage, margin, liquidation_price

### Get Trades

```python
delta.trades -> List[Dict]
```

### Historical Data

```python
import pendulum

# Using pendulum DateTime objects (recommended)
end_time = pendulum.now(tz="Asia/Kolkata")
start_time = end_time.subtract(days=7)  # Last 7 days

candles = delta.historical(
    symbol="BTCUSD",
    resolution="5",
    from_time=start_time,
    to_time=end_time,
)

# Using string timestamps
candles = delta.historical(
    symbol="BTCUSD",
    resolution="15",
    from_time="2024-01-01 00:00:00",
    to_time="2024-01-02 00:00:00",
)

# Using Unix timestamps (integers)
candles = delta.historical(
    symbol="BTCUSD",
    resolution="60",
    from_time=1609459200,
    to_time=1609545600,
)
```

**Resolution options:**
- Minutes: `1, 3, 5, 15, 30, 60, 120, 240, 360, 720`
- Days: `D`
- Weeks: `W`
- Months: `M`

**Returns:** List of candles with `time, open, high, low, close, volume`

### Other Methods

```python
delta.margins          # Get wallet balances
delta.profile          # Get user profile
delta.ltp(symbol)      # Get last traded price
delta.orderbook(symbol, limit=20)  # Get orderbook
delta.get_products()   # Get all products
delta.instrument_symbol(symbol)    # Get product details
```

## Pre/Post Hooks

### Pre-hooks (order_place, order_modify)
Automatically transform standard order parameters to Delta format:
- `side`: BUY/SELL → buy/sell
- `order_type`: LIMIT → limit_order
- `product_type`: NRML → carryforward
- `price` → limit_price
- `trigger_price` → stop_price

### Post-hooks (orders, trades, positions)
Automatically transform Delta responses to standard format:
- `id` → order_id
- `size` → quantity
- `limit_price` → price
- `state` → status
- `filled_size` → filled_quantity

## Override Configuration

Edit `delta.yaml` to customize field mappings:

```yaml
orders:
  id: order_id
  symbol: symbol
  size: quantity
  limit_price: price
```

## Error Handling

All methods include try-except blocks and return:
- `None` or `{}` on error for single objects
- `[{}]` or `[]` on error for lists
- Print error messages with traceback

## Rate Limits

Delta Exchange API rate limits:
- **Default quota:** 10,000 requests per 5 minutes
- **Weights:**
  - Get Orders/Positions/Balances: 3
  - Place/Edit/Cancel Order: 5
  - Get Order History/Fills: 10
  - Batch Orders: 25

## Testing

Run the example:

```bash
python examples/delta_example.py
```

## Comparison with Flattrade/Zerodha

| Feature | Delta | Flattrade | Zerodha |
|---------|-------|-----------|---------|
| Auth | API Key/Secret | User/Pass/PIN | API Key + TOTP |
| Order Place | ✅ | ✅ | ✅ |
| Order Modify | ✅ | ✅ | ✅ |
| Order Cancel | ✅ | ✅ | ✅ |
| Positions | ✅ | ✅ | ✅ |
| Trades | ✅ | ✅ | ✅ |
| Historical | ✅ | ✅ | ✅ |
| Pre-hooks | ✅ | ✅ | ✅ |
| Post-hooks | ✅ | ✅ | ✅ |
| Overrides | ✅ | ✅ | ✅ |

## API Documentation

Full Delta Exchange API docs: https://docs.delta.exchange

## Support

For issues with Delta Exchange API:
- Email: support@delta.exchange
- Docs: https://docs.delta.exchange

For issues with this integration:
- Check error messages and tracebacks
- Verify API key permissions
- Ensure IP is whitelisted
