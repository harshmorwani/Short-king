import json
from websocket import create_connection

URL = "wss://lbkperpws.lbank.com/ws"

print("Connecting to LBank...")

ws = create_connection(URL, timeout=20)

payload = {
    "action": "request",
    "request": "kbar",
    "kbar": "1hr",
    "pair": "BTCUSDT",
    "size": "2"
}

print("Sending request...")
ws.send(json.dumps(payload))

print("Waiting for response...")

try:
    while True:
        message = ws.recv()
        print("RESPONSE:")
        print(message)
        break
finally:
    ws.close()

print("Test finished.")
