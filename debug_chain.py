"""
Run this once to see what Delta's actual option symbols look like.
python debug_chain.py
"""
import requests
import os
from dotenv import load_dotenv
load_dotenv()

BASE_URL = os.getenv("BASE_URL", "https://api.delta.exchange")

r = requests.get(f"{BASE_URL}/v2/products", params={"contract_types": "call_options", "states": "live"})
products = r.json().get("result", [])

btc = [p for p in products if "BTC" in p.get("symbol", "")]
print(f"Total BTC calls found: {len(btc)}\n")
print("Sample symbols (first 15):")
for p in btc[:15]:
    print(f"  symbol: {p.get('symbol')}")
    print(f"  strike: {p.get('strike_price')}")
    print(f"  mark:   {p.get('mark_price')}")
    print(f"  settle: {p.get('settlement_time','')[:20]}")
    print()
