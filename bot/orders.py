"""
orders.py – Order business-logic layer.

Sits between the CLI and the raw BinanceFuturesClient.
Responsible for:
  - Calling validators
  - Invoking the client
  - Formatting a human-readable summary
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .client import BinanceFuturesClient
from .logging_config import get_logger
from .validators import (
    validate_order_type,
    validate_price,
    validate_quantity,
    validate_side,
    validate_stop_price,
    validate_symbol,
)

logger = get_logger(__name__)


@dataclass
class OrderRequest:
    """Validated order parameters."""

    symbol: str
    side: str
    order_type: str
    quantity: str
    price: Optional[str] = None
    stop_price: Optional[str] = None
    time_in_force: str = "GTC"

    def summary(self) -> str:
        parts = [
            f"  Symbol     : {self.symbol}",
            f"  Side       : {self.side}",
            f"  Type       : {self.order_type}",
            f"  Quantity   : {self.quantity}",
        ]
        if self.price:
            parts.append(f"  Price      : {self.price}")
        if self.stop_price:
            parts.append(f"  Stop Price : {self.stop_price}")
        if self.order_type == "LIMIT":
            parts.append(f"  TIF        : {self.time_in_force}")
        return "\n".join(parts)


@dataclass
class OrderResult:
    """Parsed order response."""

    order_id: int
    symbol: str
    status: str
    side: str
    order_type: str
    orig_qty: str
    executed_qty: str
    avg_price: str
    raw: Dict[str, Any] = field(repr=False)

    def summary(self) -> str:
        lines = [
            f"  Order ID   : {self.order_id}",
            f"  Status     : {self.status}",
            f"  Symbol     : {self.symbol}",
            f"  Side       : {self.side}",
            f"  Type       : {self.order_type}",
            f"  Orig Qty   : {self.orig_qty}",
            f"  Exec Qty   : {self.executed_qty}",
            f"  Avg Price  : {self.avg_price}",
        ]
        return "\n".join(lines)


class OrderManager:
    """High-level order operations."""

    def __init__(self, client: BinanceFuturesClient):
        self._client = client

    # ── Public interface ──────────────────────────────────────────────────────

    def build_request(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str | float,
        price: Optional[str | float] = None,
        stop_price: Optional[str | float] = None,
        time_in_force: str = "GTC",
    ) -> OrderRequest:
        """
        Validate all inputs and return an OrderRequest.
        Raises ValueError on any validation failure.
        """
        v_symbol = validate_symbol(symbol)
        v_side = validate_side(side)
        v_type = validate_order_type(order_type)
        v_qty = validate_quantity(quantity)
        v_price = validate_price(price, v_type)
        v_stop = validate_stop_price(stop_price, v_type)

        return OrderRequest(
            symbol=v_symbol,
            side=v_side,
            order_type=v_type,
            quantity=v_qty,
            price=v_price,
            stop_price=v_stop,
            time_in_force=time_in_force.upper(),
        )

    def place(self, req: OrderRequest) -> OrderResult:
        """
        Submit the order to the exchange and return a structured OrderResult.
        Propagates BinanceAPIError / BinanceNetworkError on failures.
        """
        logger.info("Submitting order: %s", req)
        raw = self._client.place_order(
            symbol=req.symbol,
            side=req.side,
            order_type=req.order_type,
            quantity=req.quantity,
            price=req.price,
            stop_price=req.stop_price,
            time_in_force=req.time_in_force,
        )
        result = self._parse_response(raw)
        logger.info(
            "Order placed | id=%s status=%s execQty=%s avgPrice=%s",
            result.order_id,
            result.status,
            result.executed_qty,
            result.avg_price,
        )
        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_response(raw: Dict[str, Any]) -> OrderResult:
        return OrderResult(
            order_id=raw.get("orderId", 0),
            symbol=raw.get("symbol", ""),
            status=raw.get("status", "UNKNOWN"),
            side=raw.get("side", ""),
            order_type=raw.get("type", ""),
            orig_qty=raw.get("origQty", "0"),
            executed_qty=raw.get("executedQty", "0"),
            avg_price=raw.get("avgPrice", raw.get("price", "0")),
            raw=raw,
        )
