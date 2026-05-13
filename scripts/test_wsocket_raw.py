import json, time
import websocket

ws = websocket.WebSocket()
ws.connect("wss://public-socket.india.delta.exchange")
print("Connected to public socket")

ws.send(json.dumps({"type": "subscribe", "payload": {"channels": [{"name": "ticker", "symbols": ["BTCUSD"]}]}}))
print("Subscribed, waiting for ticks...")

for i in range(5):
    ws.settimeout(10)
    try:
        msg = json.loads(ws.recv())
        t = msg.get("type")
        d = json.dumps(msg)[:300]
        print(f"[{t}] {d}")
        if t == "ticker":
            print("GOT TICKER DATA!")
            break
    except Exception as e:
        print(f"error: {e}")
        break

ws.close()
