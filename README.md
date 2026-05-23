# Crypto Options Bot — Deployment Guide
### Short Strangle on BTC Options | Delta Exchange | Paper Trading

---

## One-Time Setup (do this today, takes 15 minutes)

### Step 1 — Push code to GitHub

1. Go to [github.com](https://github.com) → Sign in / Create free account
2. Click **New Repository**
   - Name: `crypto-options-bot`
   - Set to **Private** (your API keys are in .env — never make this public)
   - Click **Create repository**
3. On your PC, open terminal in your bot folder and run:

```bash
git init
git add .
git commit -m "initial bot setup"
git remote add origin https://github.com/YOUR_USERNAME/crypto-options-bot.git
git push -u origin main
```

> Replace `YOUR_USERNAME` with your actual GitHub username.

---

### Step 2 — Add your API keys as Codespace Secrets (IMPORTANT)

Never push your real `.env` file with API keys to GitHub.

1. Go to: **github.com → Settings → Codespaces → Secrets**
2. Add these secrets one by one:

| Secret Name | Value |
|---|---|
| `DELTA_API_KEY` | your Delta Exchange API key |
| `DELTA_API_SECRET` | your Delta Exchange API secret |

These will be auto-injected into your Codespace as environment variables.

---

### Step 3 — Add .env to .gitignore

Create a file called `.gitignore` in your bot folder with this content:

```
.env
__pycache__/
*.pyc
.refact/
```

This prevents your `.env` from ever being pushed to GitHub.

---

## Every Morning (6:30 AM routine)

### Step 4 — Open Codespace

1. Go to **github.com/YOUR_USERNAME/crypto-options-bot**
2. Click green **Code** button → **Codespaces** tab
3. Click **Create codespace on main** (first time) or open existing one
4. Wait ~30 seconds for it to load — you get a full VS Code in the browser

---

### Step 5 — Install dependencies (first time only)

In the Codespace terminal at the bottom:

```bash
pip install -r requirements.txt
```

---

### Step 6 — Set your API keys in the Codespace terminal

Since your `.env` is gitignored, run this once per new Codespace session:

```bash
cp .env.example .env
```

Then open `.env` in the editor and paste your API keys.

**OR** if you set Codespace Secrets in Step 2, just run:

```bash
echo "DELTA_API_KEY=$DELTA_API_KEY" >> .env
echo "DELTA_API_SECRET=$DELTA_API_SECRET" >> .env
```

---

### Step 7 — Run the bot

```bash
python bot.py
```

You will see:
```
============================================================
TRADE MODE      : PAPER
INITIAL CAPITAL : $313.00 USDT
SYMBOL          : BTCUSDT
UNDERLYING      : BTC
============================================================
Waiting for WebSocket connection...
LIVE PRICE : 75524.31
```

Bot is now live. Entry will trigger automatically between 7-9 AM IST.

---

### Step 8 — Monitor from your phone

Once running, you can:
- Close the laptop — Codespace keeps running in the cloud
- Reopen github.com on phone browser → your Codespace → see the terminal

---

### Step 9 — Download your trades.csv after session

After the bot runs and exits (or you Ctrl+C after 9 AM):

```bash
# In Codespace terminal — check your trades
cat trades.csv
```

To download:
1. Right-click `trades.csv` in the file explorer panel on the left
2. Click **Download**
3. Open in Excel or Google Sheets for analysis

---

## Codespace Free Tier Limits

| Limit | Amount |
|---|---|
| Free hours/month | 60 hours |
| Your daily session | ~2 hours (7-9 AM) |
| Sessions per month | ~30 sessions free |
| Storage | 15 GB |

**You will never hit the limit for paper trading.**

---

## Troubleshooting

**Bot says "Waiting for WebSocket connection" forever**
→ Delta Exchange API might be down. Check [status.delta.exchange](https://status.delta.exchange)

**No strikes found during entry window**
→ Run `python debug_chain.py` to see what the options chain is returning

**Codespace disconnects / times out**
→ Just reopen it from github.com — your files are saved, just re-run `python bot.py`

**trades.csv is empty**
→ No trade triggered yet (entry window may have passed) or bot was stopped before any exit

---

## Files Reference

| File | Purpose |
|---|---|
| `bot.py` | Main loop — entry, monitoring, exit |
| `delta_api.py` | All Delta Exchange API calls |
| `strategy.py` | Entry/exit logic, strike selection |
| `websocket_handler.py` | Live BTC price feed |
| `config.py` | All settings loaded from .env |
| `logger.py` | Writes trades to trades.csv |
| `debug_chain.py` | Test options chain fetch without running full bot |
| `.env` | Your private config — never push to GitHub |
| `trades.csv` | Paper trade log — your analysis data |

---

## Current Strategy Settings

| Parameter | Value | Meaning |
|---|---|---|
| Entry window | 7–9 AM IST | Only enters during this window |
| Target premium | ~$100 per leg | Sells OTM strike closest to $100 |
| Stop loss | 1.5x premium | Exit if premium rises 50% |
| Target | 95% decay | Exit if premium falls to 5% of entry |
| Trailing SL activates | 40% profit | Locks in gains once 40% profit hit |
| Trailing SL distance | 15% | Trails 15% behind peak profit |
| Leverage | 2x | Conservative — paper mode only |
| Capital | $313 USDT | ₹30,000 equivalent |
