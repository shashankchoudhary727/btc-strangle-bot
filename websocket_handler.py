import json
import websocket
import threading


class LivePriceFeed:
    def __init__(self, symbol="BTCUSDT"):
        self.symbol = symbol
        self.socket_url = "wss://socket.delta.exchange"
        self.current_price = None
        self.connected = False

    # ------------------------------------------------------------------ #
    #  FIX #5: Parse Delta's actual v2/ticker payload structure
    #  Delta sends: { "type": "v2/ticker", "symbol": "...", "data": { ... } }
    #  The price fields live inside data{}, not at the top level.
    # ------------------------------------------------------------------ #
    def on_message(self, ws, message):
        try:
            data = json.loads(message)

            msg_type = data.get("type", "")

            # Acknowledge subscription confirmation — no price here
            if msg_type == "subscriptions":
                print(f"Subscribed to channels: {data}")
                return

            # v2/ticker is the channel we subscribed to
            if msg_type == "v2/ticker":
                ticker = data.get("data") or data  # payload is nested under 'data'
                price = (
                    ticker.get("mark_price")
                    or ticker.get("spot_price")
                    or ticker.get("last_price")
                    or ticker.get("close")
                )
                if price is not None:
                    self.current_price = float(price)

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
