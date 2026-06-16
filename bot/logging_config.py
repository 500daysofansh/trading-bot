"""
Structured logging configuration for the trading bot.
Logs are written to both console (INFO+) and a rotating file (DEBUG+).
"""

import logging
import logging.handlers
import os
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "trading_bot.log"


def setup_logging(log_level: str = "DEBUG") -> logging.Logger:
    """
    Configure root logger with:
      - A rotating file handler (logs/trading_bot.log)  → DEBUG and above
      - A console (StreamHandler)                        → INFO and above

    Returns the root logger.
    """
    LOG_DIR.mkdir(exist_ok=True)

    numeric_level = getattr(logging, log_level.upper(), logging.DEBUG)

    root = logging.getLogger()
    if root.handlers:          # avoid duplicate handlers on re-import
        return root

    root.setLevel(logging.DEBUG)

    # ── File handler ────────────────────────────────────────────────────────
    file_fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(file_fmt)

    # ── Console handler ──────────────────────────────────────────────────────
    console_fmt = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    ch = logging.StreamHandler()
    ch.setLevel(numeric_level)
    ch.setFormatter(console_fmt)

    root.addHandler(fh)
    root.addHandler(ch)

    return root


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper – call after setup_logging() has run."""
    return logging.getLogger(name)
