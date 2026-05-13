# Symbols Protocol - Design Notes

## Purpose
Broker-agnostic symbol data access from master CSV downloads. Handles:
- Download → normalize → store
- Key → value lookups
- ATM calculation
- Filter by moneyness
- Find closest premium
- Websocket token conversion

## Symbol TypedDict
Core data structure representing a row from master CSV:

```python
class Symbol(TypedDict):
    exchange: ExchangeLiteral
    tradingsymbol: str
    token: str | int      # broker-specific, can be str or int
    expiry_date: str      # e.g. '28MAY2024'
    strike: int           # 0 for futures/index
    option_type: OptionsLiteral | None  # None for futures/index
    lot_size: int
```

## Methods Summary

| Method | Purpose | When Used |
|--------|---------|-----------|
| `__init__` | Initialize + load data | Once at setup |
| `download` | Fetch raw from broker API | Once (cached) |
| `normalize` | Convert to standard columns | After download |
| `load` | Cache check + load | On init |
| `find(key)` | Get value (expiry_date, lot_size, etc) | Pre-trade |
| `get_value` | Generic key→value lookup | Pre-trade |
| `get_row` | Get first row matching key=value | Pre-trade |
| `get_rows` | Get all rows matching key=value | Pre-trade |
| `atm_strike(ltp, diff)` | Static: calculate ATM strike | Pre-trade |
| `filter_by_moneyness` | Get rows by distance from ATM | Pre-trade (moneyness mode) |
| `get_atm_rows` | Get 25 rows on each side of ATM | Pre-trade (premium mode) |
| `to_ws_tokens` | Convert Symbol → ws_token strings | Pre-trade (premium mode) |
| `from_ws_token` | Build lookup: ws_token → Symbol | Pre-trade (premium mode) |
| `find_closest_premium` | Find tradingsymbol closest to target premium | Pre-trade (premium mode) |

## Two Trading Modes

### 1. Moneyness-Based Trade
Direct, no websocket needed:
```
User: ltp=24156, distance=+3, c_or_p='CE'
→ symbols.filter_by_moneyness(ltp, distance, c_or_p)
→ tradingsymbol
→ Trade
```

### 2. Premium-Based Trade
Requires websocket for LTP:
```
User: premium=250, c_or_p='CE', ltp=24156
→ symbols.get_atm_rows(ltp, c_or_p)
→ symbols.to_ws_tokens(rows) → ws_tokens
→ Build lookup: ws_token → tradingsymbol (via from_ws_token)
→ wserver.subscribe(ws_tokens)
→ wserver returns {ws_token: ltp}
→ Apply lookup → {tradingsymbol: ltp}
→ symbols.find_closest_premium(quotes, premium, c_or_p)
→ tradingsymbol to trade
→ Unsubscribe non-traded ws_tokens
→ Trade
```

## Key Insights

1. **diff is derived, not input** - calculated from adjacent strike prices after download
2. **DEPTH=25 is constant** - used by `get_atm_rows`, not passed as parameter
3. **ws_token format varies by broker** - handled via yaml config:
   - Flattrade: `{exchange}|{token}` (e.g. 'NFO|12345')
   - Zerodha: `{token}` (e.g. '12345')
4. **from_ws_token is for lookup building only** - not used during trading
5. **Post-init, symbols not needed during trading** - caller uses pre-built lookup

## YAML Config Example (flattrade.yaml)

```yaml
normalize:
  TradingSymbol: tradingsymbol
  Optiontype: option_type
  StrikePrice: strike
  Token: token
  Expiry: expiry_date
  Lotsize: lot_size
  Exchange: exchange

ws_token_format: '{exchange}|{token}'
```

## @post Decorator
Handles column renaming via yaml config. Applied to `normalize` method:

```python
@post
def normalize(self, raw: dict) -> pd.DataFrame:
    # raw has broker columns
    # @post renames to standard columns
    return df
```

## @overload for Type Safety
Used on `find()` and `get_value()` to narrow return types:

```python
symbols.find(key='lot_size')  # returns int
symbols.find(key='expiry_date')  # returns str
symbols.get_value('strike', 24100, 'tradingsymbol')  # returns str
```

## Constants
- `DEPTH = 25` - strikes on each side of ATM (constant)

## Exchange Literals
```python
ExchangeLiteral = Literal['NSE', 'BSE', 'BFO', 'NFO', 'MCX', 'NCDEX']
```

## Options Literal
```python
OptionsLiteral = Literal['CE', 'PE']
```