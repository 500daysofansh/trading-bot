"""
client.py – Low-level Binance Futures Testnet REST client.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .logging_config import get_logger

logger = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
TESTNET_BASE_URL = "https://testnet.binancefuture.com"
DEFAULT_RECV_WINDOW = 5000
REQUEST_TIMEOUT = 10


# ── Exceptions ───────────────────────────────────────────────────────────────
class BinanceClientError(Exception):
    pass


class BinanceAPIError(BinanceClientError):
    def __init__(self, status_code: int, code: int, msg: str):
        self.status_code = status_code
        self.code = code
        self.msg = msg
        super().__init__(f"[HTTP {status_code}] Binance error {code}: {msg}")


class BinanceNetworkError(BinanceClientError):
    pass


# ── Client ───────────────────────────────────────────────────────────────────
class BinanceFuturesClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = TESTNET_BASE_URL,
        recv_window: int = DEFAULT_RECV_WINDOW,
    ):
        if not api_key or not api_secret:
            raise BinanceClientError("api_key and api_secret must not be empty.")

        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._recv_window = recv_window

        self._session = self._build_session()

        # ✅ Time sync with Binance server
        self._time_offset = self._get_server_time() - int(time.time() * 1000)

    # ── Public API ────────────────────────────────────────────────────────────

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        price: Optional[str] = None,
        stop_price: Optional[str] = None,
        time_in_force: str = "GTC",
    ) -> Dict[str, Any]:

        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }

        if order_type in {"LIMIT", "STOP"}:
            params["price"] = price
            params["timeInForce"] = time_in_force

        if order_type in {"STOP_MARKET", "STOP"} and stop_price:
            params["stopPrice"] = stop_price

        logger.info(
            "Placing order | symbol=%s side=%s type=%s qty=%s",
            symbol, side, order_type, quantity
        )

        return self._signed_post("/fapi/v1/order", params)

    def get_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        return self._signed_get("/fapi/v1/order", {"symbol": symbol, "orderId": order_id})

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        return self._signed_delete("/fapi/v1/order", {"symbol": symbol, "orderId": order_id})

    def get_account(self) -> Dict[str, Any]:
        return self._signed_get("/fapi/v2/account", {})

    def get_exchange_info(self) -> Dict[str, Any]:
        return self._get("/fapi/v1/exchangeInfo", {})

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist={500, 502, 503, 504},
            allowed_methods={"GET", "POST", "DELETE"},
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _get_server_time(self) -> int:
        """Fetch Binance server time"""
        url = self._base_url + "/fapi/v1/time"
        resp = self._session.get(url, timeout=REQUEST_TIMEOUT)
        return resp.json()["serverTime"]

    def _sign(self, query_string: str) -> str:
        return hmac.new(
            self._api_secret.encode(),
            query_string.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _headers(self) -> Dict[str, str]:
        return {
            "X-MBX-APIKEY": self._api_key,
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _add_auth(self, params: Dict[str, Any]) -> str:
        """Add timestamp + recvWindow + signature"""
        params["recvWindow"] = self._recv_window

        # ✅ Fixed timestamp (with offset)
        params["timestamp"] = int(time.time() * 1000) + self._time_offset

        qs = urlencode(params)
        signature = self._sign(qs)
        return f"{qs}&signature={signature}"

    # ── HTTP methods ──────────────────────────────────────────────────────────

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = self._base_url + path
        try:
            resp = self._session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            raise BinanceNetworkError(f"GET error: {e}") from e
        return self._handle_response(resp)

    def _signed_get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = self._base_url + path
        qs = self._add_auth(params)
        try:
            resp = self._session.get(url, params=qs, headers=self._headers(), timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            raise BinanceNetworkError(f"GET error: {e}") from e
        return self._handle_response(resp)

    def _signed_post(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = self._base_url + path
        body = self._add_auth(params)
        try:
            resp = self._session.post(url, data=body, headers=self._headers(), timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            raise BinanceNetworkError(f"POST error: {e}") from e
        return self._handle_response(resp)

    def _signed_delete(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = self._base_url + path
        qs = self._add_auth(params)
        try:
            resp = self._session.delete(url, params=qs, headers=self._headers(), timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            raise BinanceNetworkError(f"DELETE error: {e}") from e
        return self._handle_response(resp)

    @staticmethod
    def _handle_response(resp: requests.Response) -> Dict[str, Any]:
        try:
            data = resp.json()
        except ValueError:
            raise BinanceAPIError(resp.status_code, -1, "Invalid JSON response")

        if not resp.ok or ("code" in data and data["code"] < 0):
            raise BinanceAPIError(
                resp.status_code,
                data.get("code", resp.status_code),
                data.get("msg", "Unknown error"),
            )

        return data