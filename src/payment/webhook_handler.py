"""Webhook handler for Prodamus payment notifications."""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from .models import ProdamusWebhookPayload

logger = logging.getLogger("content-producer")


class ProdamusWebhookHandler:
    """Handles incoming Prodamus payment webhooks."""

    def __init__(self, secret_key: str) -> None:
        self.secret_key = secret_key

    def verify(self, raw_body: bytes, signature_header: str | None) -> bool:
        """Verify Prodamus HMAC-SHA256 signature. Refuses all webhooks if secret_key is not set."""
        if not self.secret_key:
            logger.critical("Prodamus secret_key not set — REFUSING webhook (signature verification impossible)")
            return False
        if not signature_header:
            logger.warning("Prodamus webhook received without X-Signature header")
            return False
        expected = hmac.new(
            self.secret_key.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)

    def parse(self, form_data: dict[str, Any]) -> ProdamusWebhookPayload:
        """Parse Prodamus form-encoded webhook payload."""
        return ProdamusWebhookPayload(**form_data)
