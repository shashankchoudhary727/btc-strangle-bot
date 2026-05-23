import csv
import os
from datetime import datetime

TRADE_FILE = "trades.csv"

HEADERS = [
    "timestamp",
    "trade_mode",
    "symbol",
    "entry_hour",       # NEW: which hour (0-23) this strangle was entered
    "side",
    "entry_price",
    "exit_price",
    "quantity",
    "stop_loss",
    "target",
    "pnl",
    "capital_after_trade",
    "exit_reason",      # NEW: TARGET / TRAILING SL / HARD SL / MANUAL EXIT
]

class TradeLogger:

    def __init__(self):
        self.initialize()

    def initialize(self):
        if not os.path.exists(TRADE_FILE):
            with open(TRADE_FILE, mode="w", newline="") as f:
                csv.writer(f).writerow(HEADERS)

    def log_trade(
        self,
        trade_mode,
        symbol,
        entry_hour,
        side,
        entry_price,
        exit_price,
        quantity,
        stop_loss,
        target,
        pnl,
        capital,
        exit_reason,
    ):
        with open(TRADE_FILE, mode="a", newline="") as f:
            csv.writer(f).writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                trade_mode,
                symbol,
                entry_hour,
                side,
                round(entry_price, 4),
                round(exit_price,  4),
                quantity,
                round(stop_loss,   4),
                round(target,      4),
                round(pnl,         4),
                round(capital,     4),
                exit_reason,
            ])
