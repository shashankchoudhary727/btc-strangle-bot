from config import (
    STOP_LOSS_PERCENT,
    TARGET_PERCENT,
    ENTRY_START_HOUR,
    ENTRY_END_HOUR,
    TARGET_PREMIUM,
    PREMIUM_TOLERANCE
)


class OptionSellingStrategy:

    # ------------------------------------------------------------------ #
    #  Stop-loss / Target on PREMIUM (not underlying price)
    # ------------------------------------------------------------------ #
    def calculate_stop_loss(self, premium):
        """SL = premium expands by STOP_LOSS_PERCENT (e.g. 2x = 200% of entry)."""
        return premium * (1 + STOP_LOSS_PERCENT / 100)

    def calculate_target(self, premium):
        """Target = premium decays by TARGET_PERCENT (e.g. 95% decay)."""
        return premium * (1 - TARGET_PERCENT / 100)

    # ------------------------------------------------------------------ #
    #  Entry window
    # ------------------------------------------------------------------ #
    def should_enter_trade(self, current_hour):
        if ENTRY_START_HOUR <= ENTRY_END_HOUR:
            return ENTRY_START_HOUR <= current_hour <= ENTRY_END_HOUR
        else:
            # Window crosses midnight
            return current_hour >= ENTRY_START_HOUR or current_hour <= ENTRY_END_HOUR

    # ------------------------------------------------------------------ #
    #  Exit check on PREMIUM
    # ------------------------------------------------------------------ #
    def should_exit_trade(self, current_premium, stop_loss, target):
        """
        current_premium : live mark price of the option leg
        stop_loss       : upper premium limit (we sold, so rising premium = loss)
        target          : lower premium limit (premium decay = profit)
        """
        if current_premium >= stop_loss:
            print("STOP LOSS HIT")
            return True
        if current_premium <= target:
            print("TARGET HIT")
            return True
        return False

    # ------------------------------------------------------------------ #
    #  Strike scanner  (FIX #4 — was completely missing)
    # ------------------------------------------------------------------ #
    def scan_strikes(self, options_chain, spot_price):
        """
        From the full options chain, find the OTM call and OTM put whose
        mark_price is closest to TARGET_PREMIUM (default $100).

        - OTM call = strike above spot
        - OTM put  = strike below spot
        - Picks the closest-to-target from each side, no hard rejection.
        - Only rejects if mark_price is 0 or None (no market for that strike).

        Returns:
            { 'call': {...}, 'put': {...} }  or None if chain is empty.
        """
        calls = options_chain.get("calls", [])
        puts  = options_chain.get("puts",  [])

        print(f"Spot price: {spot_price}")
        print(f"Total calls in chain: {len(calls)}, Total puts: {len(puts)}")

        # OTM = strike above spot for calls, below spot for puts
        otm_calls = [c for c in calls if c["strike_price"] > spot_price]
        otm_puts  = [p for p in puts  if p["strike_price"] < spot_price]

        print(f"OTM calls: {len(otm_calls)}, OTM puts: {len(otm_puts)}")

        # Filter out strikes with no mark price at all
        liquid_calls = [c for c in otm_calls if c["mark_price"] > 0]
        liquid_puts  = [p for p in otm_puts  if p["mark_price"] > 0]

        print(f"Liquid OTM calls: {len(liquid_calls)}, Liquid OTM puts: {len(liquid_puts)}")

        if not liquid_calls and not liquid_puts:
            print("No liquid OTM options found. Chain may be empty or expiry filter too strict.")
            return None

        # If one side is missing, we can't form a strangle
        if not liquid_calls:
            print("No liquid OTM calls found.")
            return None
        if not liquid_puts:
            print("No liquid OTM puts found.")
            return None

        # Pick closest premium to TARGET_PREMIUM on each side
        best_call = min(liquid_calls, key=lambda x: abs(x["mark_price"] - TARGET_PREMIUM))
        best_put  = min(liquid_puts,  key=lambda x: abs(x["mark_price"] - TARGET_PREMIUM))

        print(f"SELECTED CALL : {best_call['symbol']} | Strike: {best_call['strike_price']} | Premium: ${best_call['mark_price']:.2f} (target ${TARGET_PREMIUM})")
        print(f"SELECTED PUT  : {best_put['symbol']}  | Strike: {best_put['strike_price']}  | Premium: ${best_put['mark_price']:.2f} (target ${TARGET_PREMIUM})")

        # Warn if significantly off target but still proceed
        call_diff = abs(best_call["mark_price"] - TARGET_PREMIUM)
        put_diff  = abs(best_put["mark_price"]  - TARGET_PREMIUM)
        if call_diff > PREMIUM_TOLERANCE or put_diff > PREMIUM_TOLERANCE:
            print(f"WARNING: Best available premiums are outside ±${PREMIUM_TOLERANCE} tolerance. Proceeding anyway.")

        return {"call": best_call, "put": best_put}
