import time
from datetime import datetime, date

from config import (
    SYMBOL,
    LOT_SIZE,
    CHECK_INTERVAL,
    TRADE_MODE,
    INITIAL_CAPITAL,
    UNDERLYING,
    TRAILING_SL_ACTIVATION_PCT,
    TRAILING_SL_DISTANCE_PCT,
    MAX_CONCURRENT_STRANGLES,
    ENTRY_HOURS,
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

capital = INITIAL_CAPITAL

# 24-hour mode: track which hours have already been entered
# Key: (date, hour) → True once a strangle is opened in that hour
entered_hours = set()

# Active strangles: list of {call_leg, put_leg, entry_hour}
# One per hour — up to MAX_CONCURRENT_STRANGLES open at once
active_strangles = []

print("=" * 60)
print(f"TRADE MODE            : {TRADE_MODE}")
print(f"INITIAL CAPITAL       : ${capital:.2f} USDT")
print(f"SYMBOL                : {SYMBOL}")
print(f"UNDERLYING            : {UNDERLYING}")
print(f"MAX OPEN STRANGLES    : {MAX_CONCURRENT_STRANGLES}")
print(f"MODE                  : 24-HOUR (one entry per hour)")
print("=" * 60)

# Wait for WebSocket
while not feed.connected:
    print("Waiting for WebSocket connection...")
    time.sleep(1)

# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #
def make_leg(info):
    entry = info["mark_price"]
    return {
        "product_id":         info["product_id"],
        "symbol":             info["symbol"],
        "entry_premium":      entry,
        "stop_loss":          strategy.calculate_stop_loss(entry),
        "target":             strategy.calculate_target(entry),
        "exited":             False,
        "best_pnl_pct":       0.0,
        "trailing_sl":        None,
        "last_known_premium": entry,
        "exit_reason":        None,
    }

def update_trailing_sl(leg, pnl_pct):
    if pnl_pct > leg["best_pnl_pct"]:
        leg["best_pnl_pct"] = pnl_pct

    if leg["best_pnl_pct"] >= TRAILING_SL_ACTIVATION_PCT:
        trailing_floor   = leg["best_pnl_pct"] - TRAILING_SL_DISTANCE_PCT
        trailing_premium = leg["entry_premium"] * (1 - trailing_floor / 100)
        leg["trailing_sl"] = trailing_premium

    return leg

def format_balance(balance: dict) -> str:
    return (
        f"Available: ${balance['available']:.2f} | "
        f"Used: ${balance['used']:.2f} | "
        f"Total: ${balance['total']:.2f}"
    )

def process_leg(leg, leg_name, entry_hour):
    """Monitor one leg. Returns updated leg."""
    if leg is None or leg["exited"]:
        return leg

    live_premium = api.get_option_mark_price(leg["symbol"])
    if live_premium == 0.0:
        live_premium = leg["last_known_premium"]
        print(f"  {leg_name} | WARNING: mark price 0 — using last known ${live_premium:.2f}")
    else:
        leg["last_known_premium"] = live_premium

    pnl_pct = ((leg["entry_premium"] - live_premium) / leg["entry_premium"]) * 100
    leg     = update_trailing_sl(leg, pnl_pct)

    effective_sl  = leg["stop_loss"]
    trailing_tag  = ""
    if leg["trailing_sl"] is not None:
        effective_sl = min(leg["stop_loss"], leg["trailing_sl"])
        trailing_tag = f" [TSL: ${leg['trailing_sl']:.2f} | Peak: {leg['best_pnl_pct']:.1f}%]"

    print(
        f"  {leg_name} | {leg['symbol']} | "
        f"Entry: ${leg['entry_premium']:.2f} | "
        f"Live: ${live_premium:.2f} | "
        f"PnL%: {pnl_pct:.1f}% | "
        f"SL: ${effective_sl:.2f} | "
        f"Target: ${leg['target']:.2f}"
        f"{trailing_tag}"
    )

    if strategy.should_exit_trade(live_premium, effective_sl, leg["target"]):
        if TRADE_MODE == "PAPER":
            exit_resp = {"success": True}
        else:
            exit_resp = api.place_market_order(
                product_id=leg["product_id"],
                size=LOT_SIZE, side="buy"
            )

        if exit_resp:
            global capital
            pnl = (leg["entry_premium"] - live_premium) * LOT_SIZE
            capital += pnl

            if live_premium <= leg["target"]:
                exit_reason = "TARGET"
            elif leg["trailing_sl"] is not None and live_premium >= leg["trailing_sl"]:
                exit_reason = "TRAILING SL"
            else:
                exit_reason = "HARD SL"
            leg["exit_reason"] = exit_reason

            balance_after = api.get_wallet_balance()

            logger.log_trade(
                trade_mode  = TRADE_MODE,
                symbol      = leg["symbol"],
                side        = "SELL",
                entry_hour  = entry_hour,
                entry_price = leg["entry_premium"],
                exit_price  = live_premium,
                quantity    = LOT_SIZE,
                stop_loss   = leg["stop_loss"],
                target      = leg["target"],
                pnl         = pnl,
                capital     = capital,
                exit_reason = exit_reason,
            )

            print(f"  {leg_name} CLOSED | {exit_reason} | Exit: ${live_premium:.2f} | PnL: ${pnl:.2f} | Capital: ${capital:.2f}")
            print(f"  WALLET | {format_balance(balance_after)}")
            leg["exited"] = True

    return leg

# ------------------------------------------------------------------ #
#  Main loop
# ------------------------------------------------------------------ #
while True:
    try:
        now           = datetime.now()
        current_hour  = now.hour
        today         = date.today()
        hour_key      = (today, current_hour)
        current_price = feed.current_price

        if current_price is None:
            print("Waiting for live price...")
            time.sleep(1)
            continue
        if (datetime.now() - feed.last_update).seconds > 60:
            print("WARNING: Price feed stale >60s — check WebSocket")
        # ---------------------------------------------------------- #
        #  ENTRY — once per hour, if slot not already taken
        # ---------------------------------------------------------- #
        if (hour_key not in entered_hours and current_hour in ENTRY_HOURS):
            if len(active_strangles) < MAX_CONCURRENT_STRANGLES:

                print("=" * 60)
                print(f"NEW HOUR [{current_hour:02d}:xx] — entering strangle #{len(active_strangles)+1}")

                balance = api.get_wallet_balance()
                print(f"WALLET BEFORE ENTRY | {format_balance(balance)}")

                chain   = api.get_options_chain(underlying=UNDERLYING)
                strikes = strategy.scan_strikes(chain, current_price)

                if strikes is None:
                    print("No suitable strikes found — skipping this hour.")
                    entered_hours.add(hour_key)     # mark as attempted so we don't retry
                    time.sleep(CHECK_INTERVAL)
                    continue

                call_info = strikes["call"]
                put_info  = strikes["put"]

                if TRADE_MODE == "PAPER":
                    call_order = {"success": True}
                    put_order  = {"success": True}
                else:
                    api.set_leverage(call_info["product_id"])
                    api.set_leverage(put_info["product_id"])
                    call_order = api.place_market_order(
                        product_id=call_info["product_id"], size=LOT_SIZE, side="sell"
                    )
                    put_order = api.place_market_order(
                        product_id=put_info["product_id"],  size=LOT_SIZE, side="sell"
                    )

                if call_order and put_order:
                    strangle = {
                        "call_leg":   make_leg(call_info),
                        "put_leg":    make_leg(put_info),
                        "entry_hour": current_hour,
                        "entry_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    active_strangles.append(strangle)
                    entered_hours.add(hour_key)

                    balance_at_entry = api.get_wallet_balance()
                    print(f"STRANGLE ENTERED @ Hour {current_hour:02d}")
                    print(f"  CALL | {strangle['call_leg']['symbol']} | Entry: ${strangle['call_leg']['entry_premium']:.2f}")
                    print(f"  PUT  | {strangle['put_leg']['symbol']}  | Entry: ${strangle['put_leg']['entry_premium']:.2f}")
                    print(f"WALLET AT ENTRY | {format_balance(balance_at_entry)}")
                    print("=" * 60)

            else:
                print(f"Hour {current_hour:02d} — max concurrent strangles ({MAX_CONCURRENT_STRANGLES}) reached. Waiting for exits.")

        # ---------------------------------------------------------- #
        #  MONITOR all active strangles
        # ---------------------------------------------------------- #
        if active_strangles:
            print("=" * 60)
            print(f"MONITORING {len(active_strangles)} STRANGLE(S) | BTC: ${current_price:,.2f}")
            print("=" * 60)

            completed = []
            for i, strangle in enumerate(active_strangles):
                h = strangle["entry_hour"]
                print(f"--- Strangle #{i+1} (entered Hour {h:02d}) ---")

                strangle["call_leg"] = process_leg(strangle["call_leg"], "CALL", h)
                strangle["put_leg"]  = process_leg(strangle["put_leg"],  "PUT",  h)

                if strangle["call_leg"]["exited"] and strangle["put_leg"]["exited"]:
                    print(f"--- Strangle #{i+1} (Hour {h:02d}) COMPLETE ---")
                    completed.append(i)

            # Remove completed strangles (reverse order to preserve indices)
            for i in reversed(completed):
                active_strangles.pop(i)

            # Auto-shutdown: all 24 hours attempted AND no open strangles
            if today != last_reset_date:
                entered_hours.clear()
                last_reset_date = today
                print(f"New day — hourly slots reset for {today}")

        time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\nBOT STOPPED MANUALLY")
        # Save any open legs at last known price
        for strangle in active_strangles:
            for leg, name in [(strangle["call_leg"], "CALL"), (strangle["put_leg"], "PUT")]:
                if leg and not leg["exited"]:
                    live = leg["last_known_premium"]
                    pnl  = (leg["entry_premium"] - live) * LOT_SIZE
                    capital += pnl
                    logger.log_trade(
                        trade_mode  = TRADE_MODE,
                        symbol      = leg["symbol"],
                        side        = "SELL",
                        entry_hour  = strangle["entry_hour"],
                        entry_price = leg["entry_premium"],
                        exit_price  = live,
                        quantity    = LOT_SIZE,
                        stop_loss   = leg["stop_loss"],
                        target      = leg["target"],
                        pnl         = pnl,
                        capital     = capital,
                        exit_reason = "MANUAL EXIT",
                    )
                    print(f"{name} (Hour {strangle['entry_hour']:02d}) manually closed — logged at ${live:.2f} | PnL: ${pnl:.2f}")
        print(f"FINAL CAPITAL : ${capital:.2f} USDT")
        break

    except Exception as e:
        print(f"BOT ERROR : {e}")
        time.sleep(CHECK_INTERVAL)
