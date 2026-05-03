"""Subscription service — manages user subscription lifecycle."""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from .models import (
    Subscription,
    SubscriptionTier,
    PaymentTransaction,
    ProdamusWebhookPayload,
    CreateSubscriptionRequest,
    SubscriptionResponse,
)
from .prodamus_client import ProdamusClient

logger = logging.getLogger("content-producer")

# ── Tier configuration ────────────────────────────────────────

TIER_CONFIG: dict[str, dict] = {
    "free":      {"price": 0,    "period_days": None},
    "pro":       {"price": 990,  "period_days": 30},
    "enterprise":{"price": 4990, "period_days": 30},
}


class SubscriptionService:
    """Manages subscriptions: create, activate, cancel, renew."""

    def __init__(
        self,
        db_client: object,
        prodamus: Optional[ProdamusClient] = None,
    ) -> None:
        self.db = db_client
        self.prodamus = prodamus

    # ── Read ─────────────────────────────────────────────────────

    async def get_subscription(self, user_id: str) -> Optional[Subscription]:
        """Get active or most recent subscription for user."""
        try:
            result = await self.db.table("subscriptions")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .limit(1)\
                .execute()
            rows = result.data if hasattr(result, "data") else []
            if not rows:
                return None
            # Ensure status is up-to-date
            sub = Subscription(**rows[0])
            if sub.status == "active" and sub.expires_at and sub.expires_at < datetime.now(timezone.utc):
                sub.status = "expired"
                await self._update_subscription(sub.id, {"status": "expired"})
            return sub
        except Exception as exc:
            logger.error("DB error getting subscription for %s: %s", user_id, exc)
            return None

    # ── Create (free / paid) ─────────────────────────────────────

    async def create_subscription(
        self,
        req: CreateSubscriptionRequest,
    ) -> SubscriptionResponse:
        """Create a subscription. Free tiers activate immediately, paid redirect to payment."""
        sub_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)

        if req.tier == SubscriptionTier.free:
            # Free — activate immediately
            sub = Subscription(
                id=sub_id,
                user_id=req.user_id,
                tier=req.tier,
                status="active",
                started_at=created_at,
                expires_at=None,  # free = no expiry
                created_at=created_at,
                updated_at=created_at,
                auto_renew=False,
            )
            await self._save_subscription(sub.model_dump())
            return SubscriptionResponse(
                id=sub.id,
                user_id=sub.user_id,
                tier=sub.tier,
                status=sub.status,
                started_at=sub.started_at,
                expires_at=sub.expires_at,
                created_at=sub.created_at,
                updated_at=sub.updated_at,
            )

        # Paid — create pending + get payment link via Prodamus
        tier_cfg = TIER_CONFIG.get(req.tier.value, {})
        sub = Subscription(
            id=sub_id,
            user_id=req.user_id,
            tier=req.tier,
            status="pending",
            created_at=created_at,
            updated_at=created_at,
            auto_renew=req.auto_renew,
        )
        await self._save_subscription(sub.model_dump())

        # Create transaction
        txn_id = str(uuid.uuid4())
        txn = PaymentTransaction(
            id=txn_id,
            subscription_id=sub_id,
            user_id=req.user_id,
            amount=tier_cfg.get("price", 0),
            currency="RUB",
            status="pending",
            provider="prodamus",
            metadata={"tier": req.tier.value},
        )
        await self._save_transaction(txn.model_dump())

        # Get payment link
        payment_url: Optional[str] = None
        if self.prodamus:
            from .prodamus_client import ProdamusSubscriptionRequest
            prodamus_req = ProdamusSubscriptionRequest(
                order_id=sub_id,
                customer_email=req.user_id + "@content-producer.local",
                product_name=f"Content Producer — {req.tier.value}",
                product_price=tier_cfg.get("price", 0),
                subscription_period="month",
            )
            try:
                prodamus_resp = await self.prodamus.create_subscription(prodamus_req)
                payment_url = prodamus_resp.payment_link
                await self._update_transaction(txn_id, {
                    "provider_payment_id": prodamus_resp.order_id,
                    "metadata": {**txn.metadata, "payment_link": payment_url},
                })
            except Exception as exc:
                logger.error("Prodamus create_subscription failed: %s", exc)
                payment_url = None

        return SubscriptionResponse(
            id=sub.id,
            user_id=sub.user_id,
            tier=sub.tier,
            status="pending",
            started_at=None,
            expires_at=None,
            payment_url=payment_url,
            created_at=sub.created_at,
            updated_at=sub.updated_at,
        )

    # ── Webhook ────────────────────────────────────────────────

    async def handle_webhook(self, payload: ProdamusWebhookPayload) -> bool:
        """Process Prodamus payment webhook — activate / fail / renew subscription."""
        order_id = payload.order_id
        if not order_id:
            logger.warning("Prodamus webhook missing order_id")
            return False

        # Find subscription
        try:
            result = await self.db.table("subscriptions").select("*").eq("id", order_id).limit(1).execute()
            rows = result.data if hasattr(result, "data") else []
            if not rows:
                logger.warning("Subscription %s not found for webhook", order_id)
                return False
            sub = Subscription(**rows[0])
        except Exception as exc:
            logger.error("DB error in webhook handler: %s", exc)
            return False

        status = payload.payment_status.lower()
        updated_at = datetime.now(timezone.utc)

        if status in ("success", "paid", "completed"):
            # Activate subscription
            tier_cfg = TIER_CONFIG.get(sub.tier.value, {})
            period_days = tier_cfg.get("period_days", 30)
            started_at = datetime.now(timezone.utc)
            expires_at = started_at + timedelta(days=period_days)

            updates = {
                "status": "active",
                "started_at": started_at.isoformat(),
                "expires_at": expires_at.isoformat(),
                "updated_at": updated_at.isoformat(),
                "payment_provider": "prodamus",
                "provider_subscription_id": payload.subscription_id,
            }
            await self._update_subscription(sub.id, updates)

            # Mark transaction success
            await self.db.table("payment_transactions")\
                .update({
                    "status": "success",
                    "completed_at": updated_at.isoformat(),
                    "provider_payment_id": payload.order_id,
                })\
                .eq("subscription_id", sub.id)\
                .execute()

            logger.info("Subscription %s activated via Prodamus webhook", sub.id)
            return True

        elif status in ("failed", "cancelled", "declined"):
            await self._update_subscription(sub.id, {"status": "failed", "updated_at": updated_at.isoformat()})
            await self.db.table("payment_transactions")\
                .update({"status": "failed", "completed_at": updated_at.isoformat()})\
                .eq("subscription_id", sub.id)\
                .execute()
            logger.warning("Subscription %s payment failed", sub.id)
            return True

        else:
            logger.info("Unhandled Prodamus webhook status: %s for order %s", status, order_id)
            return True

    # ── DB helpers ──────────────────────────────────────────────

    async def _save_subscription(self, data: dict) -> None:
        await self.db.table("subscriptions").insert(data).execute()

    async def _update_subscription(self, sub_id: str, updates: dict) -> None:
        await self.db.table("subscriptions").update(updates).eq("id", sub_id).execute()

    async def _save_transaction(self, data: dict) -> None:
        await self.db.table("payment_transactions").insert(data).execute()

    async def _update_transaction(self, txn_id: str, updates: dict) -> None:
        await self.db.table("payment_transactions").update(updates).eq("id", txn_id).execute()
