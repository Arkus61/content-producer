"""Async Prodamus payment client.

Implements subscription creation, payment-status polling, and webhook
signature verification (HMAC-SHA256) for the Prodamus Russian payment gateway.

Prodamus docs: https://prodamus.ru/help/
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from pydantic import BaseModel, Field

try:
    import aiohttp
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "aiohttp is required for ProdamusClient. "
        "Install it with: pip install aiohttp"
    ) from exc

from src.config import settings

logger = logging.getLogger(__name__)


# ── Pydantic models for request / response ──────────────────────────────────

class ProdamusSubscriptionRequest(BaseModel):
    """Payload for creating a Prodamus subscription."""

    order_id: str = Field(..., description="Unique merchant order id")
    customer_email: str = Field(..., description="Customer e-mail")
    customer_phone: Optional[str] = Field(default=None, description="Customer phone")
    product_name: str = Field(..., description="Human-readable product name")
    product_price: float = Field(..., gt=0, description="Price in rubles")
    currency: str = Field(default="RUB", description="ISO-4217 currency code")
    subscription_period: str = Field(default="month", description="month / week / day")
    subscription_duration: Optional[int] = Field(default=None, description="Number of periods")
    success_url: Optional[str] = Field(default=None)
    fail_url: Optional[str] = Field(default=None)
    webhook_url: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProdamusSubscriptionResponse(BaseModel):
    """Response returned after subscription creation."""

    payment_link: str = Field(..., description="URL to redirect the customer to")
    order_id: str
    transaction_id: Optional[str] = Field(default=None)
    status: str = Field(default="pending")
    raw_response: Optional[Dict[str, Any]] = Field(default=None, exclude=True)


class ProdamusPaymentStatusResponse(BaseModel):
    """Parsed payment-status payload."""

    order_id: str
    transaction_id: Optional[str] = None
    status: str  # pending, success, failed, refunded, etc.
    amount: Optional[float] = None
    currency: Optional[str] = None
    paid_at: Optional[str] = None
    customer_email: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = Field(default=None, exclude=True)


# ── Client ──────────────────────────────────────────────────────────────────

class ProdamusClient:
    """Async HTTP client for Prodamus API.

    Usage:
        client = ProdamusClient()
        resp = await client.create_subscription(
            ProdamusSubscriptionRequest(order_id="ord-123", ...)
        )
        status = await client.get_payment_status("ord-123")
        assert client.verify_signature(webhook_body, signature_header)
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key or settings.prodamus_api_key
        self.secret_key = secret_key or settings.prodamus_secret_key
        self.base_url = (base_url or settings.prodamus_base_url).rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    # ── session lifecycle ──────────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "ProdamusClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ── headers / helpers ──────────────────────────────────────────────────

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

    @staticmethod
    def _build_form_data(payload: Dict[str, Any]) -> str:
        """Flatten nested dicts (metadata) into dotted keys and URL-encode."""
        flat: Dict[str, Any] = {}

        def _flatten(obj: Any, prefix: str = "") -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    _flatten(v, f"{prefix}{k}.")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    _flatten(v, f"{prefix}{i}.")
            else:
                flat[prefix.rstrip(".")] = obj if obj is not None else ""

        _flatten(payload)
        return urlencode(flat, doseq=True, encoding="utf-8")

    # ── API methods ──────────────────────────────────────────────────────

    async def create_subscription(
        self,
        request: ProdamusSubscriptionRequest,
        *,
        success_url: Optional[str] = None,
        fail_url: Optional[str] = None,
        webhook_url: Optional[str] = None,
    ) -> ProdamusSubscriptionResponse:
        """Create a subscription and return a payment link.

        Prodamus API accepts form-urlencoded data.  The `api_key` is included
        in the payload.  On success Prodamus returns JSON with the field
        ``payment_link`` (or ``url`` depending on the environment).
        """
        if not self.api_key:
            raise RuntimeError("Prodamus API key is not configured")

        payload: Dict[str, Any] = {
            "api_key": self.api_key,
            "order_id": request.order_id,
            "customer_email": request.customer_email,
            "product_name": request.product_name,
            "product_price": request.product_price,
            "currency": request.currency,
            "subscription_period": request.subscription_period,
            "success_url": success_url or request.success_url or settings.prodamus_success_url,
            "fail_url": fail_url or request.fail_url or settings.prodamus_fail_url,
        }

        if request.customer_phone:
            payload["customer_phone"] = request.customer_phone

        if request.subscription_duration is not None:
            payload["subscription_duration"] = request.subscription_duration

        if webhook_url or request.webhook_url or settings.prodamus_webhook_url:
            payload["notification_url"] = (
                webhook_url or request.webhook_url or settings.prodamus_webhook_url
            )

        if request.metadata:
            payload["metadata"] = request.metadata

        body = self._build_form_data(payload)
        url = f"{self.base_url}/api/v1/subscription/create"

        session = await self._get_session()
        logger.debug("Prodamus create_subscription → %s  order_id=%s", url, request.order_id)

        async with session.post(url, data=body, headers=self._headers()) as resp:
            text = await resp.text()
            if resp.status >= 400:
                logger.error(
                    "Prodamus create_subscription error %s: %s", resp.status, text
                )
                resp.raise_for_status()

            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                # Some demo environments return plain text URL
                data = {"payment_link": text.strip(), "order_id": request.order_id}

        payment_link = (
            data.get("payment_link")
            or data.get("url")
            or data.get("link")
            or data.get("payment_url")
        )

        if not payment_link:
            raise RuntimeError(
                f"Prodamus did not return a payment link. Response: {data}"
            )

        return ProdamusSubscriptionResponse(
            payment_link=payment_link,
            order_id=request.order_id,
            transaction_id=data.get("transaction_id") or data.get("payment_id"),
            status=data.get("status", "pending"),
            raw_response=data,
        )

    async def get_payment_status(
        self,
        order_id: str,
        *,
        transaction_id: Optional[str] = None,
    ) -> ProdamusPaymentStatusResponse:
        """Poll Prodamus for the current status of an order."""
        if not self.api_key:
            raise RuntimeError("Prodamus API key is not configured")

        params: Dict[str, Any] = {
            "api_key": self.api_key,
            "order_id": order_id,
        }
        if transaction_id:
            params["transaction_id"] = transaction_id

        query = urlencode(params, doseq=True)
        url = f"{self.base_url}/api/v1/payment/status?{query}"

        session = await self._get_session()
        logger.debug("Prodamus get_payment_status → %s  order_id=%s", url, order_id)

        async with session.get(url, headers=self._headers()) as resp:
            text = await resp.text()
            if resp.status >= 400:
                logger.error(
                    "Prodamus get_payment_status error %s: %s", resp.status, text
                )
                resp.raise_for_status()

            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Prodamus returned non-JSON status response: {text}"
                ) from exc

        return ProdamusPaymentStatusResponse(
            order_id=order_id,
            transaction_id=data.get("transaction_id") or data.get("payment_id"),
            status=data.get("status", "unknown"),
            amount=data.get("amount"),
            currency=data.get("currency"),
            paid_at=data.get("paid_at") or data.get("payment_date"),
            customer_email=data.get("customer_email"),
            raw_response=data,
        )

    # ── Webhook signature verification ─────────────────────────────────────

    def verify_signature(self, body: bytes, signature: str) -> bool:
        """Verify HMAC-SHA256 webhook signature.

        Prodamus sends the signature in the ``X-Signature`` header (or as a
        form-field named ``signature``).  The body must be the raw request
        bytes (before any parsing).
        """
        if not self.secret_key:
            logger.warning(
                "Prodamus secret key is not configured; webhook signature "
                "verification is impossible"
            )
            return False

        expected = hmac.new(
            self.secret_key.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        # Timing-safe compare to prevent timing attacks
        return hmac.compare_digest(expected, signature)

    def verify_form_signature(self, form_data: Dict[str, Any]) -> bool:
        """Verify signature when Prodamus sends it inside form fields.

        Prodamus may include a ``signature`` field together with the rest of
        the POST data.  This helper strips the field, serialises the remaining
        data in the same way Prodamus does (key-ordered JSON string) and
        validates the HMAC.
        """
        if "signature" not in form_data:
            return False

        signature = str(form_data.pop("signature"))
        # Prodamus canonical representation: sorted keys, no spaces, utf-8
        body = json.dumps(form_data, sort_keys=True, separators=(",", ":"))
        return self.verify_signature(body.encode("utf-8"), signature)


# ── Standalone helpers (usable without instatiating the client) ─────────────

def verify_prodamus_signature(body: bytes, signature: str, secret_key: str) -> bool:
    """Low-level helper – verify a raw body against a hex HMAC-SHA256 signature."""
    expected = hmac.new(secret_key.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
