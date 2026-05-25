# BTC Short Strangle Bot 🤖

An automated options trading bot that runs short strangle strategies on BTC
options via Delta Exchange. Built in Python, runs 24/7 on a VPS, and designed
for systematic data collection and strategy validation.

> ⚠️ This bot is currently in **paper trading mode** — using live market data
> with simulated execution. Not financial advice. Trade at your own risk.

---

## What It Does

The bot automatically:
- Scans the Delta Exchange options chain every hour
- Identifies OTM call and put contracts with premium closest to $100/leg
- Enters a short strangle (sells both legs simultaneously)
- Monitors positions in real-time via WebSocket + ticker polling
- Exits based on predefined rules — no manual intervention needed
- Logs every trade to `trades.csv` for analysis

One strangle per hour. 24 strangles per day. Fully automated.

---

## Strategy Logic

| Parameter                  | Value                        |
|----------------------------|------------------------------|
| Instrument                 | BTC Options — Delta Exchange |
| Structure                  | Short Strangle (OTM Call + OTM Put) |
| Expiry                     | Tomorrow's expiry only       |
| Entry Frequency            | Once per hour (00:00 to 23:00 UTC) |
| Target Premium             | ~$100 per leg                |
| Profit Target              | 95% premium decay            |
| Hard Stop Loss             | 1.5x entry premium           |
| Trailing SL Activation     | 40% profit on leg            |
| Trailing SL Trail          | 15% behind peak profit       |
| Max Concurrent Strangles   | 4 (capital safety guard)     |
| Leverage                   | 2x                           |

---

## Tech Stack

- **Language:** Python 3.10+
- **Exchange:** Delta Exchange (Crypto Options)
- **Data:** Live market data via Delta REST API + WebSocket
- **Execution:** Paper trading (simulated fills, real prices)
- **Infrastructure:** Hostinger VPS — Ubuntu 24.04 LTS
- **Storage:** CSV-based trade logging

---

## Project Structure

```
btc-strangle-bot/
├── bot.py                 # Main entry point — orchestrates the loop
├── strategy.py            # Entry/exit logic, SL calculations
├── delta_api.py           # Delta Exchange REST API wrapper
├── websocket_handler.py   # Real-time price feed via WebSocket
├── config.py              # Configuration loader
├── logger.py              # Trade logging to trades.csv
├── debug_chain.py         # Options chain debugging utility
├── .env.example           # Environment variable template
├── config.json            # Strategy parameters
├── trades.csv             # Auto-generated trade log
└── README.md
```

---

## Installation

### Prerequisites

- Python 3.10 or higher
- A Delta Exchange account (testnet or live)
- API key and secret from Delta Exchange
- A Linux VPS or local machine (Ubuntu recommended)

### Step 1 — Clone the Repository

```bash
git clone https://github.com/shashankchoudhary727/btc-strangle-bot.git
cd btc-strangle-bot
```

### Step 2 — Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3 — Configure Environment Variables

```bash
cp .env.example .env
nano .env
```

Fill in your credentials:

```
DELTA_API_KEY=your_api_key_here
DELTA_API_SECRET=your_api_secret_here
```

### Step 4 — Configure Strategy Parameters

Edit `config.json` to adjust strategy settings:

```json
{
  "target_premium": 100,
  "profit_target_pct": 0.95,
  "hard_sl_multiplier": 1.5,
  "trailing_sl_activation_pct": 0.40,
  "trailing_sl_trail_pct": 0.15,
  "max_concurrent_strangles": 4,
  "leverage": 2
}
```

### Step 5 — Run the Bot

**Locally:**
```bash
python3 bot.py
```

**On VPS (runs after terminal close):**
```bash
nohup python3 bot.py > bot_log.txt 2>&1 &
```

**Check live logs:**
```bash
tail -f bot_log.txt
```

**Stop the bot:**
```bash
kill $(pgrep -f bot.py)
```

---

## Trade Logging

Every entry and exit is automatically logged to `trades.csv`:

| Column         | Description                                      |
|----------------|--------------------------------------------------|
| timestamp      | UTC time of the event                            |
| entry_hour     | Which hourly cycle (0–23)                        |
| leg            | call or put                                      |
| entry_premium  | Premium collected at entry ($)                   |
| exit_premium   | Premium at exit ($)                              |
| pnl            | Realized PnL for the leg ($)                     |
| exit_reason    | target / hard_sl / trailing_sl / manual          |

**Download trades from VPS to local machine:**
```bash
scp root@YOUR_VPS_IP:/root/btc-strangle-bot/trades.csv C:\Users\YourName\Desktop\trades.csv
```

---

## Improving Bot Performance

These are the levers available to tune strategy behavior:

**1. Adjust Target Premium**
The bot targets ~$100/leg. In low volatility environments, this may be hard
to fill cleanly. You can lower `target_premium` to $70–80 to increase fill
frequency at the cost of lower premium collected per trade.

**2. Tighten or Loosen Hard SL**
Currently set at 1.5x entry premium. A tighter SL (1.2x) reduces max loss
per leg but increases the chance of getting stopped out on normal fluctuations.
A looser SL (2x) gives more room but increases drawdown risk.

**3. Trailing SL Activation Threshold**
Currently activates at 40% profit. Activating earlier (25–30%) locks in
profit sooner but may exit too early on legs that would have hit 95% decay.
Activating later (50–60%) lets winners run but gives back more profit if
market reverses.

**4. Skip High-Volatility Hours**
If data over multiple sessions shows consistent Hard SL hits during specific
UTC hours (e.g., US market open, major news windows), those hours can be
excluded by adding a `no_trade_hours` list to `config.json`.

**5. Expiry Selection**
Bot currently targets tomorrow's expiry only. Shorter expiries have faster
decay (good for this strategy) but less liquidity. This is a parameter worth
monitoring over time.

---

## Risk Disclosure

- **This is not financial advice.** This bot is a research and automation tool.
- Short strangles carry **unlimited loss potential** on the call side in theory.
  Hard SL and max concurrent position limits exist to contain this.
- Crypto options markets are **highly volatile** and can gap through stop levels.
- The bot is in **paper trading mode** — it does not place real orders or touch
  real capital in its current state.
- Past paper trading results do not guarantee live trading performance.
- Never allocate capital you cannot afford to lose entirely.

---

## Current Status

| Metric        | Value           |
|---------------|-----------------|
| Mode          | Paper Trading   |
| Live Since    | May 24, 2025    |
| Days of Data  | Ongoing         |
| Bot Uptime    | 24/7 on VPS     |

*Results and analysis will be published as data accumulates.*

---

## Author

**Shanks** — Project Manager by day, algo trader by night.
Building this in public on YouTube: [Mindset2Money](https://youtube.com/@Mindset2Money)

---

## License

MIT License — use freely, modify openly, trade responsibly.