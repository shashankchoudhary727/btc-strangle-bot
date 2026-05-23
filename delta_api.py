import time
import hmac
import hashlib
import json
import requests
from datetime import datetime, timedelta

from config import API_KEY, API_SECRET, BASE_URL, LEVERAGE


class DeltaAPI:
    def __init__(self):
        self.session = requests.Session()

    # ------------------------------------------------------------------ #
    #  Auth
    # ------------------------------------------------------------------ #
    def generate_signature(self, method, endpoint, timestamp, body=""):
        message = method + timestamp + endpoint + body
        return hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()

    def send_request(self, method, endpoint, payload=None, params=None):
        timestamp = str(int(time.time()))
        body = json.dumps(payload) if payload else ""

        query_string = ""
        if params:
            query_string = "?" + "&".join(f"{k}={v}" for k, v in params.items())

        signature = self.generate_signature(method, endpoint + query_string, timestamp, body)

        headers = {
            "api-key":      API_KEY,
            "timestamp":    timestamp,
            "signature":    signature,
            "Content-Type": "application/json"
        }

        url = BASE_URL + endpoint

        try:
            if method == "GET":
                response = self.session.get(url, headers=headers, params=params)
            elif method == "POST":
                response = self.session.post(url, headers=headers, data=body)
            else:
                raise ValueError("Unsupported HTTP method")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API Error: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  Orders
    # ------------------------------------------------------------------ #
    def place_market_order(self, product_id, size, side):
        """Place a market order. side = 'buy' or 'sell'."""
        endpoint = "/v2/orders"
        payload = {
            "product_id": product_id,
            "size":       size,
            "side":       side,
            "order_type": "market_order"
        }
        return self.send_request("POST", endpoint, payload)

    def set_leverage(self, product_id):
        """Set leverage for a product before placing an order."""
        endpoint = "/v2/products/leverage"
        payload = {
            "product_id": product_id,
            "leverage":   LEVERAGE
        }
        return self.send_request("POST", endpoint, payload)

    # ------------------------------------------------------------------ #
    #  Products list
    # ------------------------------------------------------------------ #
    def get_products(self, contract_type="call_options", state="live"):
        endpoint = "/v2/products"
        params = {
            "contract_types": contract_type,
            "states":         state
        }
        return self.send_request("GET", endpoint, params=params)

    # ------------------------------------------------------------------ #
    #  Live option premium for a single leg (called during monitoring)
    # ------------------------------------------------------------------ #
    def get_option_mark_price(self, symbol: str) -> float:
        """
        Returns the current mark_price for a single option symbol.
        Hits /v2/tickers?contract_types=call_options|put_options and
        looks up by symbol. Falls back to 0.0 on any error.

        Usage:
            live_price = api.get_option_mark_price("C-BTC-76200-240526")
        """
        contract_type = "call_options" if symbol.startswith("C-") else "put_options"
        endpoint = "/v2/tickers"
        params   = {"contract_types": contract_type}
        resp     = self.send_request("GET", endpoint, params=params)

        if not resp:
            return 0.0

        tickers = resp.get("result", [])
        for t in tickers:
            if t.get("symbol") == symbol:
                mark = float(t.get("mark_price") or t.get("close") or 0)
                if mark == 0:
                    bid = float(t.get("best_bid") or t.get("best_bid_price") or 0)
                    ask = float(t.get("best_ask") or t.get("best_ask_price") or 0)
                    if bid > 0 and ask > 0:
                        mark = round((bid + ask) / 2, 4)
                return mark

        return 0.0

    # ------------------------------------------------------------------ #
    #  Wallet balance  (available + used margin)
    # ------------------------------------------------------------------ #
    def get_wallet_balance(self, asset: str = "USDT") -> dict:
        """
        Returns available and used balance for the given asset.
        Delta Exchange endpoint: GET /v2/wallet/balances

        Returns:
            {
                "available": float,   # free margin
                "used":      float,   # margin in use
                "total":     float    # available + used
            }
        Falls back to zeros on error.
        """
        endpoint = "/v2/wallet/balances"
        resp = self.send_request("GET", endpoint)

        empty = {"available": 0.0, "used": 0.0, "total": 0.0}
        if not resp:
            return empty

        balances = resp.get("result", [])
        for b in balances:
            if b.get("asset_symbol") == asset or b.get("currency") == asset:
                available = float(b.get("available_balance") or b.get("available") or 0)
                used      = float(b.get("order_margin")      or b.get("used")      or 0) \
                          + float(b.get("position_margin")   or 0)
                return {
                    "available": round(available, 4),
                    "used":      round(used,      4),
                    "total":     round(available + used, 4)
                }

        return empty

    # ------------------------------------------------------------------ #
    #  Live tickers  (mark_price lives here, NOT in /v2/products)
    # ------------------------------------------------------------------ #
    def get_tickers(self, contract_type="call_options"):
        """
        Returns dict keyed by symbol -> ticker data (includes mark_price,
        best_bid, best_ask). This is the only reliable source of live
        option premiums on Delta Exchange.
        """
        endpoint = "/v2/tickers"
        params = {"contract_types": contract_type}
        resp = self.send_request("GET", endpoint, params=params)
        if not resp:
            return {}
        tickers = resp.get("result", [])
        return {t.get("symbol"): t for t in tickers if t.get("symbol")}

    # ------------------------------------------------------------------ #
    #  Expiry helpers
    # ------------------------------------------------------------------ #
    def get_tomorrow_expiry_candidates(self):
        """
        Generate all possible expiry string formats Delta may use.
        Delta has used multiple formats across different product types.
        """
        tomorrow   = datetime.utcnow() + timedelta(days=1)
        day_no_pad = str(int(tomorrow.strftime("%d")))   # '5' or '23'
        day_padded = tomorrow.strftime("%d")              # '05' or '23'
        mon3       = tomorrow.strftime("%b")              # 'May'
        mon2       = tomorrow.strftime("%m")              # '05'
        yr2        = tomorrow.strftime("%y")              # '26'
        iso_date   = tomorrow.strftime("%Y-%m-%d")        # '2026-05-23'

        return list(dict.fromkeys([                       # deduplicate, preserve order
            f"{day_no_pad}{mon3}{yr2}",                   # 23May26
            f"{day_padded}{mon3}{yr2}",                   # 23May26
            f"{day_padded}{mon2}{yr2}",                   # 230526
            f"{day_no_pad}{mon2}{yr2}",                   # 23526
            iso_date,                                      # 2026-05-23
        ]))

    # ------------------------------------------------------------------ #
    #  Options chain  (products + tickers merged)
    # ------------------------------------------------------------------ #
    def get_options_chain(self, underlying="BTC"):
        """
        Returns:
        {
            'calls': [ {product_id, symbol, strike_price, mark_price, ...} ],
            'puts':  [ {product_id, symbol, strike_price, mark_price, ...} ]
        }
        mark_price comes from /v2/tickers (not /v2/products which always returns 0).
        """
        expiry_candidates = self.get_tomorrow_expiry_candidates()
        tomorrow_iso      = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

        # Step 1: live mark prices from tickers
        print("Fetching live tickers for mark prices...")
        call_tickers = self.get_tickers(contract_type="call_options")
        put_tickers  = self.get_tickers(contract_type="put_options")
        print(f"Tickers — calls: {len(call_tickers)}, puts: {len(put_tickers)}")

        # Step 2: product list for strike_price, settlement_time, product_id
        print(f"Fetching products — expiry candidates: {expiry_candidates}")
        calls_list = (self.get_products("call_options") or {}).get("result", [])
        puts_list  = (self.get_products("put_options")  or {}).get("result", [])

        all_btc = [p.get("symbol","") for p in calls_list + puts_list if underlying in p.get("symbol","")]
        print(f"Total {underlying} symbols in products: {len(all_btc)}")
        if all_btc:
            print(f"Sample: {all_btc[:5]}")

        def matches_tomorrow(p):
            sym  = p.get("symbol", "").upper()
            stl  = p.get("settlement_time", "")
            if tomorrow_iso in stl:
                return True
            for c in expiry_candidates:
                if c.upper() in sym:
                    return True
            return False

        def extract(products, tickers):
            out = []
            for p in products:
                sym = p.get("symbol", "")
                if underlying not in sym:
                    continue
                if not matches_tomorrow(p):
                    continue

                t        = tickers.get(sym, {})
                mark     = float(t.get("mark_price")    or t.get("close")          or 0)
                best_bid = float(t.get("best_bid")      or t.get("best_bid_price") or 0)
                best_ask = float(t.get("best_ask")      or t.get("best_ask_price") or 0)

                # Fallback: mid-price
                if mark == 0 and best_bid > 0 and best_ask > 0:
                    mark = round((best_bid + best_ask) / 2, 4)

                out.append({
                    "product_id":   p.get("id"),
                    "symbol":       sym,
                    "strike_price": float(p.get("strike_price") or 0),
                    "mark_price":   mark,
                    "best_bid":     best_bid,
                    "best_ask":     best_ask,
                    "settlement":   p.get("settlement_time", ""),
                })
            return sorted(out, key=lambda x: x["strike_price"])

        calls = extract(calls_list, call_tickers)
        puts  = extract(puts_list,  put_tickers)

        print(f"After expiry filter — calls: {len(calls)}, puts: {len(puts)}")
        if calls:
            print(f"Sample call marks: {[(c['symbol'], c['mark_price']) for c in calls[:3]]}")
        if puts:
            print(f"Sample put marks:  {[(p['symbol'], p['mark_price']) for p in puts[:3]]}")

        return {"calls": calls, "puts": puts}
