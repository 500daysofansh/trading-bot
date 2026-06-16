#!/usr/bin/env python3
"""
cli.py – Command-line entry point for the Binance Futures Testnet trading bot.

Supports:
  place   – Place MARKET, LIMIT, STOP_MARKET, or STOP orders
  account – Show futures account balances
  order   – Look up an existing order by ID
  cancel  – Cancel an open order by ID

Environment variables (required for authenticated commands):
  BINANCE_API_KEY    – Testnet API key
  BINANCE_API_SECRET – Testnet API secret

Quick examples
--------------
  # Market buy
  python cli.py place --symbol BTCUSDT --side BUY --type MARKET --qty 0.001

  # Limit sell
  python cli.py place --symbol BTCUSDT --side SELL --type LIMIT --qty 0.001 --price 70000

  # Stop-market (bonus order type)
  python cli.py place --symbol BTCUSDT --side SELL --type STOP_MARKET --qty 0.001 --stop-price 60000

  # Check account balances
  python cli.py account

  # Look up an order
  python cli.py order --symbol BTCUSDT --order-id 123456789
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap

from bot.client import BinanceAPIError, BinanceClientError, BinanceNetworkError, BinanceFuturesClient
from bot.logging_config import setup_logging, get_logger
from bot.orders import OrderManager

# ── Bootstrap logging ────────────────────────────────────────────────────────
setup_logging("INFO")          # console shows INFO+; file gets everything (DEBUG+)
logger = get_logger(__name__)

# ── ANSI helpers (graceful fallback on Windows without colorama) ──────────────
def _c(code: str, text: str) -> str:
    if sys.stdout.isatty():
        return f"\033[{code}m{text}\033[0m"
    return text

GREEN  = lambda t: _c("32", t)
RED    = lambda t: _c("31", t)
YELLOW = lambda t: _c("33", t)
BOLD   = lambda t: _c("1",  t)
CYAN   = lambda t: _c("36", t)

BANNER = textwrap.dedent("""
  ╔══════════════════════════════════════════════╗
  ║   Binance Futures Testnet  •  Trading Bot    ║
  ╚══════════════════════════════════════════════╝
""")


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Place and manage Binance Futures Testnet orders.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python cli.py place --symbol BTCUSDT --side BUY  --type MARKET     --qty 0.001
              python cli.py place --symbol BTCUSDT --side SELL --type LIMIT      --qty 0.001 --price 70000
              python cli.py place --symbol BTCUSDT --side SELL --type STOP_MARKET --qty 0.001 --stop-price 60000
              python cli.py account
              python cli.py order  --symbol BTCUSDT --order-id 123456789
              python cli.py cancel --symbol BTCUSDT --order-id 123456789
        """),
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # ── place ────────────────────────────────────────────────────────────────
    place_p = sub.add_parser("place", help="Place a new order.")
    place_p.add_argument("--symbol",     required=True, help="Trading pair, e.g. BTCUSDT")
    place_p.add_argument("--side",       required=True, choices=["BUY", "SELL"], help="BUY or SELL")
    place_p.add_argument(
        "--type",
        required=True,
        dest="order_type",
        choices=["MARKET", "LIMIT", "STOP_MARKET", "STOP"],
        metavar="TYPE",
        help="Order type: MARKET | LIMIT | STOP_MARKET | STOP",
    )
    place_p.add_argument("--qty",        required=True, help="Order quantity (e.g. 0.001)")
    place_p.add_argument("--price",      default=None,  help="Limit price (required for LIMIT/STOP)")
    place_p.add_argument("--stop-price", default=None,  dest="stop_price",
                         help="Stop trigger price (required for STOP_MARKET/STOP)")
    place_p.add_argument(
        "--tif",
        default="GTC",
        dest="time_in_force",
        choices=["GTC", "IOC", "FOK"],
        help="Time-in-force for LIMIT orders (default: GTC)",
    )

    # ── account ──────────────────────────────────────────────────────────────
    sub.add_parser("account", help="Show futures account balances.")

    # ── order ────────────────────────────────────────────────────────────────
    ord_p = sub.add_parser("order", help="Look up an order by ID.")
    ord_p.add_argument("--symbol",   required=True)
    ord_p.add_argument("--order-id", required=True, type=int, dest="order_id")

    # ── cancel ───────────────────────────────────────────────────────────────
    can_p = sub.add_parser("cancel", help="Cancel an open order.")
    can_p.add_argument("--symbol",   required=True)
    can_p.add_argument("--order-id", required=True, type=int, dest="order_id")

    return parser


# ── Credential helper ─────────────────────────────────────────────────────────

def _load_credentials() -> tuple[str, str]:
    api_key    = os.environ.get("BINANCE_API_KEY", "").strip()
    api_secret = os.environ.get("BINANCE_API_SECRET", "").strip()
    if not api_key or not api_secret:
        print(RED("✗ Missing credentials."))
        print(
            "  Set environment variables:\n"
            "    export BINANCE_API_KEY=<your_key>\n"
            "    export BINANCE_API_SECRET=<your_secret>"
        )
        sys.exit(1)
    return api_key, api_secret


# ── Command handlers ──────────────────────────────────────────────────────────

def cmd_place(args: argparse.Namespace, mgr: OrderManager) -> None:
    print(BOLD("\n── Order Request ──────────────────────────────"))
    try:
        req = mgr.build_request(
            symbol=args.symbol,
            side=args.side,
            order_type=args.order_type,
            quantity=args.qty,
            price=args.price,
            stop_price=args.stop_price,
            time_in_force=args.time_in_force,
        )
    except ValueError as exc:
        print(RED(f"✗ Validation error: {exc}"))
        logger.error("Validation failed: %s", exc)
        sys.exit(2)

    print(req.summary())
    print(BOLD("\n── Submitting… ────────────────────────────────"))

    try:
        result = mgr.place(req)
    except BinanceAPIError as exc:
        print(RED(f"\n✗ API Error [{exc.code}]: {exc.msg}"))
        logger.error("API error while placing order: %s", exc)
        sys.exit(3)
    except BinanceNetworkError as exc:
        print(RED(f"\n✗ Network Error: {exc}"))
        logger.error("Network error while placing order: %s", exc)
        sys.exit(4)

    print(BOLD("\n── Order Response ─────────────────────────────"))
    print(result.summary())
    print()
    print(GREEN(f"✓ Order placed successfully! (ID: {result.order_id})"))
    logger.info("✓ Order placed successfully  id=%s status=%s", result.order_id, result.status)


def cmd_account(client: BinanceFuturesClient) -> None:
    print(BOLD("\n── Account Balances ───────────────────────────"))
    try:
        data = client.get_account()
    except (BinanceAPIError, BinanceNetworkError) as exc:
        print(RED(f"\n✗ Error: {exc}"))
        sys.exit(3)

    assets = [a for a in data.get("assets", []) if float(a.get("walletBalance", 0)) > 0]
    if not assets:
        print("  No non-zero balances found.")
    for a in assets:
        print(f"  {CYAN(a['asset']):12s}  wallet={a['walletBalance']:>16}  unrealizedPnl={a.get('unrealizedProfit', '0'):>16}")


def cmd_order(args: argparse.Namespace, client: BinanceFuturesClient) -> None:
    print(BOLD(f"\n── Order {args.order_id} ({'':─<38}"))
    try:
        data = client.get_order(args.symbol.upper(), args.order_id)
    except (BinanceAPIError, BinanceNetworkError) as exc:
        print(RED(f"\n✗ Error: {exc}"))
        sys.exit(3)

    for key in ("orderId", "symbol", "status", "side", "type", "origQty", "executedQty", "avgPrice", "price"):
        if key in data:
            print(f"  {key:15s}: {data[key]}")


def cmd_cancel(args: argparse.Namespace, client: BinanceFuturesClient) -> None:
    print(BOLD(f"\n── Cancelling order {args.order_id} ──────────────"))
    try:
        data = client.cancel_order(args.symbol.upper(), args.order_id)
    except (BinanceAPIError, BinanceNetworkError) as exc:
        print(RED(f"\n✗ Error: {exc}"))
        sys.exit(3)

    print(GREEN(f"✓ Order {data.get('orderId')} cancelled.  Status: {data.get('status')}"))


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    print(BOLD(BANNER))
    parser = build_parser()
    args   = parser.parse_args()

    api_key, api_secret = _load_credentials()

    try:
        client = BinanceFuturesClient(api_key=api_key, api_secret=api_secret)
    except BinanceClientError as exc:
        print(RED(f"✗ Client init error: {exc}"))
        sys.exit(1)

    mgr = OrderManager(client)

    if args.command == "place":
        cmd_place(args, mgr)
    elif args.command == "account":
        cmd_account(client)
    elif args.command == "order":
        cmd_order(args, client)
    elif args.command == "cancel":
        cmd_cancel(args, client)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
