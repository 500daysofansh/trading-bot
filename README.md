# Binance Futures Testnet Trading Bot

A clean, production-ready Python CLI tool for placing and managing orders on the **Binance USDT-M Futures Testnet**.

---

## Features

| Feature | Detail |
|---|---|
| Order types | `MARKET`, `LIMIT`, `STOP_MARKET` *(bonus)*, `STOP` *(bonus)* |
| Sides | `BUY` and `SELL` |
| CLI | `argparse` with full `--help`, subcommands, and validation messages |
| Logging | Rotating file (`logs/trading_bot.log`) + console; structured, non-noisy |
| Error handling | Validation errors, API errors (`BinanceAPIError`), network failures (`BinanceNetworkError`) |
| Code structure | Layered: `client.py` → `orders.py` → `cli.py` |

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py
│   ├── client.py          # Binance REST client (HMAC signing, HTTP, error handling)
│   ├── orders.py          # Order business logic + response parsing
│   ├── validators.py      # Input validation (raises ValueError on bad input)
│   └── logging_config.py  # Rotating file + console logger setup
├── cli.py                 # CLI entry point (argparse subcommands)
├── logs/
│   └── trading_bot.log    # Auto-created on first run
├── README.md
└── requirements.txt
```

---

## Setup

### 1. Get Testnet credentials

1. Go to [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Log in (GitHub SSO available)
3. Navigate to **API Key** → Generate a new key pair
4. Save your **API Key** and **Secret Key**

### 2. Clone and install

```bash
git clone https://github.com/<your-username>/trading-bot.git
cd trading-bot

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Set credentials

```bash
export BINANCE_API_KEY="your_testnet_api_key"
export BINANCE_API_SECRET="your_testnet_api_secret"
```

On Windows (PowerShell):
```powershell
$env:BINANCE_API_KEY    = "your_testnet_api_key"
$env:BINANCE_API_SECRET = "your_testnet_api_secret"
```

---

## How to Run

### Place a MARKET order

```bash
python cli.py place --symbol BTCUSDT --side BUY --type MARKET --qty 0.001
```

Expected output:
```
── Order Request ──────────────────────────────
  Symbol     : BTCUSDT
  Side       : BUY
  Type       : MARKET
  Quantity   : 0.001

── Submitting… ────────────────────────────────

── Order Response ─────────────────────────────
  Order ID   : 3801259865
  Status     : FILLED
  Symbol     : BTCUSDT
  Side       : BUY
  Type       : MARKET
  Orig Qty   : 0.001
  Exec Qty   : 0.001
  Avg Price  : 65432.10

✓ Order placed successfully! (ID: 3801259865)
```

---

### Place a LIMIT order

```bash
python cli.py place --symbol BTCUSDT --side SELL --type LIMIT --qty 0.001 --price 70000
```

Use `--tif IOC` or `--tif FOK` to override the default `GTC` time-in-force.

---

### Place a STOP_MARKET order *(bonus)*

```bash
python cli.py place --symbol BTCUSDT --side SELL --type STOP_MARKET --qty 0.001 --stop-price 60000
```

---

### Place a STOP (stop-limit) order *(bonus)*

```bash
python cli.py place --symbol BTCUSDT --side SELL --type STOP --qty 0.001 --price 59500 --stop-price 60000
```

---

### Check account balances

```bash
python cli.py account
```

---

### Look up an existing order

```bash
python cli.py order --symbol BTCUSDT --order-id 3801259865
```

---

### Cancel an open order

```bash
python cli.py cancel --symbol BTCUSDT --order-id 3801260001
```

---

### Full help

```bash
python cli.py --help
python cli.py place --help
```

---

## Logging

All runs append to `logs/trading_bot.log` (auto-created).

- **Console** → `INFO` and above (clean, user-facing messages)
- **File** → `DEBUG` and above (full request bodies, responses, errors)

The file rotates at 5 MB and keeps 3 backups.

Sample log lines:
```
2025-07-14T09:12:02 | INFO     | bot.client | Placing order | symbol=BTCUSDT side=BUY type=MARKET qty=0.001
2025-07-14T09:12:02 | DEBUG    | bot.client | POST /fapi/v1/order body=symbol=BTCUSDT&...&signature=a1b2c3...
2025-07-14T09:12:02 | DEBUG    | bot.client | HTTP 200  POST  https://testnet.binancefuture.com/fapi/v1/order
2025-07-14T09:12:02 | INFO     | bot.orders | Order placed | id=3801259865 status=FILLED execQty=0.001 avgPrice=65432.10
```

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Missing credentials | Prints instructions, exits with code 1 |
| Invalid input (bad symbol, negative qty, missing price) | Prints validation message, exits with code 2 |
| API error (e.g. insufficient margin) | Prints Binance error code + message, exits with code 3 |
| Network failure / timeout | Prints error, exits with code 4; 3 automatic retries for 5xx errors |

---

## Assumptions

- All orders use the **USDT-M Futures Testnet** (`https://testnet.binancefuture.com`).
- `positionSide` defaults to `BOTH` (one-way mode); hedge-mode is not supported.
- Quantity and price precision are passed as-is; for production use, these should be rounded to the symbol's `LOT_SIZE` / `PRICE_FILTER` from `GET /fapi/v1/exchangeInfo`.
- No `.env` file loader is included; credentials are read from environment variables only.

---

## Dependencies

```
requests>=2.31.0
urllib3>=2.0.0
```

No Binance SDK needed — all API calls use direct HMAC-signed REST requests.
