import time
from datetime import datetime, date

from config import (
    SYMBOL,
    LOT_SIZE,
    CHECK_INTERVAL,
    TRADE_MODE,
    INITIAL_CAPITAL,
    UNDERLYING,
    TRAILING_SL_ACTIVATION_PCT,   # profit % at which trailing kicks in
    TRAILING_SL_DISTANCE_PCT,     # how far behind the best profit the SL trails
)

from strategy import OptionSellingStrategy
from websocket_handler import LivePriceFeed
from delta_api import DeltaAPI
from logger import TradeLogger

# ------------------------------------------------------------------ #
#  Initialise
# ------------------------------------------------------------------ #
strategy = OptionSellingStrategy()
logger   = TradeLogger()
api      = DeltaAPI()

feed = LivePriceFeed(symbol=SYMBOL)
feed.start()

capital         = INITIAL_CAPITAL
last_trade_date = None          # one entry per calendar day

# Short strangle — two legs
call_leg = None
put_leg  = None

def legs_active():
    return call_leg is not None or put_leg is not None

print("=" * 60)
print(f"TRADE MODE      : {TRADE_MODE}")
print(f"INITIAL CAPITAL : ${capital:.2f} USDT")
print(f"SYMBOL          : {SYMBOL}")
print(f"UNDERLYING      : {UNDERLYING}")
print("=" * 60)

# Wait for WebSocket
while not feed.connected:
    print("Waiting for WebSocket connection...")
    time.sleep(1)

# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #
def make_leg(info):
    """Build a leg dict with trailing SL fields initialised."""
    entry = info["mark_price"]
    return {
        "product_id":    info["product_id"],
        "symbol":        info["symbol"],
        "entry_premium": entry,
        "stop_loss":     strategy.calculate_stop_loss(entry),   # hard SL (2x)
        "target":        strategy.calculate_target(entry),       # target (5% of entry)
        "exited":        False,
        # --- trailing stop loss tracking ---
        "best_pnl_pct":  0.0,    # highest % profit seen so far (positive = profit)
        "trailing_sl":   None,   # None = trailing not yet activated
    }

def update_trailing_sl(leg, pnl_pct):
    """
    Trailing SL logic:
    - Activates when profit reaches TRAILING_SL_ACTIVATION_PCT (e.g. 40%)
    - Trails TRAILING_SL_DISTANCE_PCT (e.g. 15%) behind the best profit seen
    - Once activated, acts as a floor — if profit falls back by that distance, exit
    - Returns updated leg dict
    """
    if pnl_pct > leg["best_pnl_pct"]:
        leg["best_pnl_pct"] = pnl_pct

    # Activate trailing once profit crosses the activation threshold
    if leg["best_pnl_pct"] >= TRAILING_SL_ACTIVATION_PCT:
        trailing_floor = leg["best_pnl_pct"] - TRAILING_SL_DISTANCE_PCT
        # Express trailing floor as a premium price
        # pnl_pct = ((entry - live) / entry) * 100  =>  live = entry * (1 - floor/100)
        trailing_premium = leg["entry_premium"] * (1 - trailing_floor / 100)
        leg["trailing_sl"] = trailing_premium   # always ratchet upward (lower premium)

    return leg

def format_balance(balance: dict) -> str:
    return (
        f"Available: ${balance['available']:.2f} | "
        f"Used: ${balance['used']:.2f} | "
        f"Total: ${balance['total']:.2f}"
    )

# ------------------------------------------------------------------ #
#  Main loop
# ------------------------------------------------------------------ #
while True:
    try:
        now           = datetime.now()
        current_hour  = now.hour
        today         = date.today()
        current_price = feed.current_price

        if current_price is None:
            print("Waiting for live price...")
            time.sleep(1)
            continue

        # ---------------------------------------------------------- #
        #  ENTRY — no open legs + entry window + not already traded
        # ---------------------------------------------------------- #
        if not legs_active():

            if last_trade_date == today:
                print(f"Already traded today ({today}). Waiting for next session.")
                time.sleep(CHECK_INTERVAL)
                continue

            if strategy.should_enter_trade(current_hour):
                print("ENTRY CONDITION MET — scanning options chain...")

                # Fetch wallet balance before entry
                balance = api.get_wallet_balance()
                print("=" * 60)
                print(f"WALLET BEFORE ENTRY | {format_balance(balance)}")
                print("=" * 60)

                chain   = api.get_options_chain(underlying=UNDERLYING)
                strikes = strategy.scan_strikes(chain, current_price)

                if strikes is None:
                    print("No suitable strikes found. Will retry next interval.")
                    time.sleep(CHECK_INTERVAL)
                    continue

                call_info = strikes["call"]
                put_info  = strikes["put"]

                # Place orders (or simulate in PAPER mode)
                if TRADE_MODE == "PAPER":
                    print("PAPER TRADE — simulating both legs")
                    call_order = {"success": True}
                    put_order  = {"success": True}
                else:
                    print("LIVE TRADE — setting leverage and placing sell orders")
                    api.set_leverage(call_info["product_id"])
                    api.set_leverage(put_info["product_id"])
                    call_order = api.place_market_order(
                        product_id=call_info["product_id"],
                        size=LOT_SIZE, side="sell"
                    )
                    put_order = api.place_market_order(
                        product_id=put_info["product_id"],
                        size=LOT_SIZE, side="sell"
                    )

                if call_order and put_order:
                    call_leg = make_leg(call_info)
                    put_leg  = make_leg(put_info)
                    last_trade_date = today

                    # Balance snapshot at entry
                    balance_at_entry = api.get_wallet_balance()

                    print("=" * 60)
                    print("STRANGLE ENTERED")
                    print(f"CALL | {call_leg['symbol']} | Entry: ${call_leg['entry_premium']:.2f} | SL: ${call_leg['stop_loss']:.2f} | Target: ${call_leg['target']:.2f}")
                    print(f"PUT  | {put_leg['symbol']}  | Entry: ${put_leg['entry_premium']:.2f} | SL: ${put_leg['stop_loss']:.2f} | Target: ${put_leg['target']:.2f}")
                    print(f"WALLET AT ENTRY | {format_balance(balance_at_entry)}")
                    print("=" * 60)

        # ---------------------------------------------------------- #
        #  MONITOR + EXIT — manage each leg independently
        # ---------------------------------------------------------- #
        else:
            print("=" * 60)
            print(f"MONITORING OPEN STRANGLE  |  Underlying: ${current_price:,.2f}")
            print("=" * 60)

            def exit_leg(leg, leg_name):
                if leg is None or leg["exited"]:
                    return leg

                # ---- FIX: fetch LIVE premium from Delta API ----
                live_premium = api.get_option_mark_price(leg["symbol"])
                if live_premium == 0.0:
                    # Fallback: keep last known value, don't exit on bad data
                    live_premium = leg.get("last_known_premium", leg["entry_premium"])
                    print(f"{leg_name} | WARNING: mark price returned 0 — using last known ${live_premium:.2f}")
                else:
                    leg["last_known_premium"] = live_premium

                pnl_pct = ((leg["entry_premium"] - live_premium) / leg["entry_premium"]) * 100

                # ---- Update trailing SL ----
                leg = update_trailing_sl(leg, pnl_pct)

                # Effective SL: tighter of hard SL or trailing SL
                effective_sl = leg["stop_loss"]
                trailing_tag = ""
                if leg["trailing_sl"] is not None:
                    effective_sl = min(leg["stop_loss"], leg["trailing_sl"])
                    trailing_tag = f" [Trailing: ${leg['trailing_sl']:.2f} | Best: {leg['best_pnl_pct']:.1f}%]"

                print(
                    f"{leg_name} | {leg['symbol']} | "
                    f"Entry: ${leg['entry_premium']:.2f} | "
                    f"Live: ${live_premium:.2f} | "
                    f"PnL%: {pnl_pct:.1f}% | "
                    f"Hard SL: ${leg['stop_loss']:.2f} | "
                    f"Target: ${leg['target']:.2f}"
                    f"{trailing_tag}"
                )

                # Exit check (uses effective SL)
                if strategy.should_exit_trade(live_premium, effective_sl, leg["target"]):

                    if TRADE_MODE == "PAPER":
                        print(f"PAPER EXIT — {leg_name}")
                        exit_resp = {"success": True}
                    else:
                        print(f"LIVE EXIT — {leg_name}")
                        exit_resp = api.place_market_order(
                            product_id=leg["product_id"],
                            size=LOT_SIZE, side="buy"
                        )

                    if exit_resp:
                        pnl = (leg["entry_premium"] - live_premium) * LOT_SIZE

                        global capital
                        capital += pnl

                        # Balance after exit
                        balance_after = api.get_wallet_balance()

                        logger.log_trade(
                            trade_mode=TRADE_MODE,
                            symbol=leg["symbol"],
                            side="SELL",
                            entry_price=leg["entry_premium"],
                            exit_price=live_premium,
                            quantity=LOT_SIZE,
                            stop_loss=leg["stop_loss"],
                            target=leg["target"],
                            pnl=pnl,
                            capital=capital
                        )

                        exit_reason = "TARGET" if live_premium <= leg["target"] else \
                                      ("TRAILING SL" if leg["trailing_sl"] and live_premium >= leg["trailing_sl"] else "HARD SL")

                        print(f"{leg_name} CLOSED | Reason: {exit_reason} | Exit: ${live_premium:.2f} | PnL: ${pnl:.2f} | Capital: ${capital:.2f}")
                        print(f"WALLET AFTER EXIT | {format_balance(balance_after)}")
                        leg["exited"] = True

                return leg

            call_leg = exit_leg(call_leg, "CALL")
            put_leg  = exit_leg(put_leg,  "PUT")
            print("=" * 60)

            # Clear legs only when BOTH have exited
            if call_leg["exited"] and put_leg["exited"]:
                print("BOTH LEGS CLOSED — strangle complete.")
                call_leg = None
                put_leg  = None

        time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("BOT STOPPED MANUALLY")
        break

    except Exception as e:
        print(f"BOT ERROR : {e}")
        time.sleep(CHECK_INTERVAL)
