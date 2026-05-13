import time, sys

from broker_ai.delta.wsocket import Wsocket

ws = Wsocket()
result = {"ticks": 0}

def on_connect():
    print("[on_connect] connected!")
    ws.subscribe(["BTCUSD"])

def on_ticks(ltp):
    result["ticks"] += 1
    print(f"[tick #{result['ticks']}] {ltp}")
    if result["ticks"] >= 3:
        ws.disconnect()

def on_error(err):
    print(f"[on_error] {err}")

def on_close():
    print("[on_close] closed")

ws.on_connect = on_connect
ws.on_ticks = on_ticks
ws.on_error = on_error
ws.on_close = on_close

print("Connecting to public socket...")
ws.connect(threaded=True)

timeout = 15
while result["ticks"] < 3 and timeout > 0:
    time.sleep(1)
    timeout -= 1

if result["ticks"] == 0:
    print("FAILED: no ticks")
    sys.exit(1)
else:
    print(f"SUCCESS: {result['ticks']} ticks")
