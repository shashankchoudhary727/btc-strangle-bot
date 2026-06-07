import json
import websocket
import threading
from datetime import datetime


class LivePriceFeed:
    def __init__(self, symbol="BTCUSDT"):
        self.symbol = symbol
        self.socket_url = "wss://socket.delta.exchange"
        self.current_price = None
        self.connected = False
        self.last_update = datetime.now()

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")

            if msg_type == "subscriptions":
                print(f"Subscribed to channels: {data}")
                return

            if msg_type == "v2/ticker":
                ticker = data.get("data") or data
                for field in ("mark_price", "spot_price", "last_price", "close"):
                    raw = ticker.get(field)
                    if raw is None:
                        continue
                    try:
                        price = float(raw)
                        if price > 0:
                            self.current_price = price
                            self.last_update = datetime.now()
                            break
                    except (ValueError, TypeError):
                        continue

        except Exception as e:
            print(f"WebSocket Message Error: {e}")

    def on_error(self, ws, error):
        print(f"WebSocket Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print("WebSocket Closed")
        self.connected = False

    def on_open(self, ws):
        print("WebSocket Connected")
        self.connected = True

        payload = {
            "type": "subscribe",
            "payload": {
                "channels": [
                    {
                        "name": "v2/ticker",
                        "symbols": [self.symbol]
                    }
                ]
            }
        }

        ws.send(json.dumps(payload))

    def start(self):
        self.ws = websocket.WebSocketApp(
            self.socket_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

        thread = threading.Thread(target=self.ws.run_forever)
        thread.daemon = True
        thread.start()