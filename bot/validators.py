"""
validators.py – Input validation for order parameters.

All public functions raise ValueError with a human-readable message on
failure; they return the (possibly coerced) value on success.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional


VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET", "STOP"}


def validate_symbol(symbol: str) -> str:
    """Return uppercased symbol; raise ValueError if blank."""
    s = symbol.strip().upper()
    if not s:
        raise ValueError("Symbol must not be empty (e.g. BTCUSDT).")
    if len(s) < 5:
        raise ValueError(f"Symbol '{s}' looks too short – expected something like BTCUSDT.")
    return s


def validate_side(side: str) -> str:
    """Return uppercased side or raise ValueError."""
    s = side.strip().upper()
    if s not in VALID_SIDES:
        raise ValueError(f"Side must be one of {sorted(VALID_SIDES)}, got '{side}'.")
    return s


def validate_order_type(order_type: str) -> str:
    """Return uppercased order type or raise ValueError."""
    t = order_type.strip().upper()
    if t not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Order type must be one of {sorted(VALID_ORDER_TYPES)}, got '{order_type}'."
        )
    return t


def validate_quantity(quantity: str | float) -> str:
    """Validate quantity is a positive number; return as string for API."""
    try:
        q = Decimal(str(quantity))
    except InvalidOperation:
        raise ValueError(f"Quantity '{quantity}' is not a valid number.")
    if q <= 0:
        raise ValueError(f"Quantity must be positive, got {q}.")
    return str(q)


def validate_price(price: Optional[str | float], order_type: str) -> Optional[str]:
    """
    Validate price:
    - Required for LIMIT / STOP orders.
    - Must be positive if provided.
    Returns string or None.
    """
    needs_price = order_type.upper() in {"LIMIT", "STOP"}

    if price is None or str(price).strip() == "":
        if needs_price:
            raise ValueError(f"Price is required for {order_type} orders.")
        return None

    try:
        p = Decimal(str(price))
    except InvalidOperation:
        raise ValueError(f"Price '{price}' is not a valid number.")
    if p <= 0:
        raise ValueError(f"Price must be positive, got {p}.")
    return str(p)


def validate_stop_price(
    stop_price: Optional[str | float], order_type: str
) -> Optional[str]:
    """Stop price is required for STOP / STOP_MARKET orders."""
    needs_stop = order_type.upper() in {"STOP", "STOP_MARKET"}

    if stop_price is None or str(stop_price).strip() == "":
        if needs_stop:
            raise ValueError(f"Stop price is required for {order_type} orders.")
        return None

    try:
        sp = Decimal(str(stop_price))
    except InvalidOperation:
        raise ValueError(f"Stop price '{stop_price}' is not a valid number.")
    if sp <= 0:
        raise ValueError(f"Stop price must be positive, got {sp}.")
    return str(sp)
