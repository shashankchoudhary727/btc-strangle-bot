import os
from dotenv import load_dotenv
load_dotenv()

API_KEY    = os.getenv("DELTA_API_KEY")
API_SECRET = os.getenv("DELTA_API_SECRET")
BASE_URL   = os.getenv("BASE_URL", "https://api.delta.exchange")

SYMBOL     = os.getenv("SYMBOL", "BTCUSDT")
UNDERLYING = os.getenv("UNDERLYING", "BTC")
LOT_SIZE   = int(os.getenv("LOT_SIZE", 1))

# Capital in USDT (Delta settles in USDT, not INR)
# ₹30,000 ≈ $313 — keep this in dollars
INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", 313))

# Leverage: 2x to 10x recommended for small capital
# Set per order via Delta API before each trade
LEVERAGE = int(os.getenv("LEVERAGE", 5))

# 24-hour research mode — one strangle per hour, all day
# MAX_CONCURRENT_STRANGLES: cap on open positions at once (capital safety)
MAX_CONCURRENT_STRANGLES = int(os.getenv("MAX_CONCURRENT_STRANGLES", 4))

# Legacy entry window (not used in 24-hour mode)
ENTRY_START_HOUR = int(os.getenv("ENTRY_START_HOUR", 0))
ENTRY_END_HOUR   = int(os.getenv("ENTRY_END_HOUR", 23))

# Exit rules: premium-based (not underlying price)
STOP_LOSS_PERCENT = float(os.getenv("STOP_LOSS_PERCENT", 100))  # 2x premium
TARGET_PERCENT    = float(os.getenv("TARGET_PERCENT", 95))       # 95% decay

# Strike selection: find OTM strike closest to TARGET_PREMIUM
TARGET_PREMIUM    = float(os.getenv("TARGET_PREMIUM", 100))      # $100 per leg
PREMIUM_TOLERANCE = float(os.getenv("PREMIUM_TOLERANCE", 80))    # accept $20–$180 range

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 2))
TRADE_MODE     = os.getenv("TRADE_MODE", "PAPER")

# Trailing stop loss:
# - TRAILING_SL_ACTIVATION_PCT : profit % at which trailing SL activates (e.g. 40 = 40% profit)
# - TRAILING_SL_DISTANCE_PCT   : how far behind the peak profit the SL trails (e.g. 15 = 15%)
# Example: if best profit was 60%, trailing SL locks in at 45% profit
TRAILING_SL_ACTIVATION_PCT = float(os.getenv("TRAILING_SL_ACTIVATION_PCT", 40))
TRAILING_SL_DISTANCE_PCT   = float(os.getenv("TRAILING_SL_DISTANCE_PCT",   15))
