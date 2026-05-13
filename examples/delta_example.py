"""
Delta Exchange Integration Example
===================================

This example demonstrates how to use the Delta Exchange integration
similar to Flattrade and Zerodha brokers.

Setup:
------
1. Get your API key and secret from https://www.delta.exchange/app/account/manageapikeys
2. Whitelist your IP address for the API key
3. Ensure API key has appropriate permissions (Trading, Read Data)

Usage:
------
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
    
    # Get historical data
    candles = delta.historical(
        symbol="BTCUSD",
        resolution="5",  # 5 minute candles
        start=1609459200,  # Unix timestamp
        end=1609545600
    )
    
    # Get margins
    margins = delta.margins
    
    # Get LTP
    ltp = delta.ltp("BTCUSD")
    
    # Get products
    products = delta.get_products()
"""

from broker_ai.delta import Delta
import pendulum


def main():
    # Initialize Delta Exchange
    delta = Delta(
        api_key="your_api_key",
        api_secret="your_api_secret"
    )
    
    # Authenticate
    print("Authenticating...")
    auth_result = delta.authenticate()
    if not auth_result:
        print("Authentication failed!")
        return
    
    print(f"Authentication successful: {auth_result}")
    
    # Get products
    print("\nGetting products...")
    products = delta.get_products()
    if products:
        print(f"Found {len(products)} products")
        if len(products) > 0:
            print(f"First product: {products[0].get('symbol', 'N/A')}")
    
    # Get margins
    print("\nGetting margins...")
    margins = delta.margins
    print(f"Margins: {margins}")
    
    # Get LTP
    print("\nGetting LTP for BTCUSD...")
    ltp = delta.ltp("BTCUSD")
    print(f"LTP: {ltp}")
    
    # Place a test order (commented out by default)
    # print("\nPlacing test order...")
    # order_id = delta.order_place(
    #     symbol="BTCUSD",
    #     side="BUY",
    #     order_type="LIMIT",
    #     quantity=100,
    #     price=45000,
    #     product_type="NRML",
    #     tag="test_order_1"
    # )
    # print(f"Order placed: {order_id}")
    
    # Get orders
    print("\nGetting orders...")
    orders = delta.orders
    print(f"Orders: {orders}")
    
    # Get positions
    print("\nGetting positions...")
    positions = delta.positions
    print(f"Positions: {positions}")
    
    # Get trades
    print("\nGetting trades...")
    trades = delta.trades
    print(f"Trades: {trades}")
    
    # Get historical data
    print("\nGetting historical data...")
    end_time = pendulum.now(tz="Asia/Kolkata")
    start_time = end_time.subtract(days=1)  # Last 24 hours
    
    candles = delta.historical(
        symbol="BTCUSD",
        resolution="15",  # 15 minute candles
        from_time=start_time,
        to_time=end_time,
    )
    
    if candles:
        print(f"Found {len(candles)} candles")
        if len(candles) > 0:
            print(f"Latest candle: {candles[-1]}")
    else:
        print("No historical data found")
    
    # Example with string timestamps
    # candles = delta.historical(
    #     symbol="BTCUSD",
    #     resolution="60",
    #     from_time="2024-01-01 00:00:00",
    #     to_time="2024-01-02 00:00:00",
    # )
    
    # Example with Unix timestamps
    # candles = delta.historical(
    #     symbol="BTCUSD",
    #     resolution="60",
    #     from_time=1609459200,
    #     to_time=1609545600,
    # )


if __name__ == "__main__":
    main()
