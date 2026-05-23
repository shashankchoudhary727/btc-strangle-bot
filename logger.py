import csv
import os
from datetime import datetime

TRADE_FILE = "trades.csv"


class TradeLogger:

    def __init__(self):
        self.initialize()

    def initialize(self):

        if not os.path.exists(TRADE_FILE):

            with open(TRADE_FILE, mode="w", newline="") as file:

                writer = csv.writer(file)

                writer.writerow([
                    "timestamp",
                    "trade_mode",
                    "symbol",
                    "side",
                    "entry_price",
                    "exit_price",
                    "quantity",
                    "stop_loss",
                    "target",
                    "pnl",
                    "capital_after_trade"
                ])


    def log_trade(
        self,
        trade_mode,
        symbol,
        side,
        entry_price,
        exit_price,
        quantity,
        stop_loss,
        target,
        pnl,
        capital
    ):

        with open(TRADE_FILE, mode="a", newline="") as file:

            writer = csv.writer(file)

            writer.writerow([
                datetime.now(),
                trade_mode,
                symbol,
                side,
                entry_price,
                exit_price,
                quantity,
                stop_loss,
                target,
                pnl,
                capital
            ])