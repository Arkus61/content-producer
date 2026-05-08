"""Tests for the payment module — Prodamus integration, webhooks, subscriptions."""

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db_client import _mem
from src.payment.models import (
    SubscriptionTier,
    CreateSubscriptionRequest,
    ProdamusWebhookPayload,
)
from src.payment.prodamus_client import (
    verify_prodamus_signature,
    ProdamusSubscriptionResponse,
    ProdamusClient,
)
from src.payment.webhook_handler import ProdamusWebhookHandler
from src.payment.subscription_service import SubscriptionService, TIER_CONFIG


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_memory():
    """Reset in-memory store before each test."""
    _mem.__init__()
    yield
    _mem.__init__()


def _make_execute_result(data):
    """Return a mock result with a .data attribute (simulates Supabase response)."""
    result = MagicMock()
    result.data = data
    return result


def _mock_db_chain(return_data=None):
    """Build a MagicMock that supports fluent .table().select().eq().order().limit().execute()
    and .table().insert().execute() and .table().update().eq().execute().

    The execute() call is an AsyncMock so it can be awaited.

    Returns (db_mock, execute_mock) so you can assert on calls.
    """
    db = MagicMock()
    execute_mock = AsyncMock(return_value=_make_execute_result(return_data or []))
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.execute = execute_mock
    db.table.return_value = chain
    return db, execute_mock


# ── ProdamusWebhookHandler Tests ───────────────────────────────────────────

class TestProdamusWebhookHandler:
    def test_verify_no_secret_key(self):
        handler = ProdamusWebhookHandler(secret_key="")
        assert handler.verify(b"body", "sig") is False

    def test_verify_no_signature_header(self):
        handler = ProdamusWebhookHandler(secret_key="sk-abc")
        assert handler.verify(b"body", None) is False

    def test_verify_valid_signature(self):
        secret = "sk-secret-123"
        body = b'{"order_id":"ord-1"}'
        expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        handler = ProdamusWebhookHandler(secret_key=secret)
        assert handler.verify(body, expected) is True

    def test_verify_invalid_signature(self):
        secret = "sk-secret-456"
        body = b'{"order_id":"ord-2"}'
        handler = ProdamusWebhookHandler(secret_key=secret)
        assert handler.verify(body, "badsig") is False

    def test_parse_valid_form_data(self):
        handler = ProdamusWebhookHandler(secret_key="sk-x")
        form = {
            "order_num": "ord-10",
            "payment_status": "success",
            "amount": "990.0",
            "currency": "RUB",
            "email": "u@b.com",
        }
        payload = handler.parse(form)
        assert isinstance(payload, ProdamusWebhookPayload)
        assert payload.order_id == "ord-10"
        assert payload.payment_status == "success"
        assert payload.amount == 990.0


# ── SubscriptionService.get_subscription ───────────────────────────────────

class TestGetSubscription:
    @pytest.mark.asyncio
    async def test_get_subscription_returns_none_when_empty(self):
        db, _ = _mock_db_chain(return_data=[])
        svc = SubscriptionService(db_client=db)
        result = await svc.get_subscription("user-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_subscription_returns_subscription(self):
        future_expiry = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        row = {
            "id": "sub-1",
            "user_id": "user-1",
            "tier": "pro",
            "status": "active",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": future_expiry,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        db, _ = _mock_db_chain(return_data=[row])
        svc = SubscriptionService(db_client=db)
        sub = await svc.get_subscription("user-1")
        assert sub is not None
        assert sub.id == "sub-1"
        assert sub.status == "active"

    @pytest.mark.asyncio
    async def test_get_subscription_expired(self):
        past_expiry = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        row = {
            "id": "sub-2",
            "user_id": "user-1",
            "tier": "pro",
            "status": "active",
            "started_at": (datetime.now(timezone.utc) - timedelta(days=35)).isoformat(),
            "expires_at": past_expiry,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=35)).isoformat(),
            "updated_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
        }
        db, _ = _mock_db_chain(return_data=[row])
        svc = SubscriptionService(db_client=db)
        sub = await svc.get_subscription("user-1")
        assert sub is not None
        assert sub.status == "expired"
        # The _update_subscription should have been called with expired status
        db.table.assert_any_call("subscriptions")
        update_call_args = db.table.return_value.update.call_args
        assert update_call_args is not None


# ── SubscriptionService.create_subscription ────────────────────────────────

class TestCreateSubscription:
    @pytest.mark.asyncio
    async def test_create_free_subscription(self):
        db, exec_mock = _mock_db_chain()
        svc = SubscriptionService(db_client=db)
        req = CreateSubscriptionRequest(
            user_id="user-1",
            tier=SubscriptionTier.free,
        )
        resp = await svc.create_subscription(req)
        assert resp.status == "active"
        assert resp.payment_url is None
        assert resp.tier == SubscriptionTier.free
        # insert should have been called
        db.table.assert_any_call("subscriptions")
        exec_mock.assert_called()

    @pytest.mark.asyncio
    async def test_create_paid_subscription_with_prodamus(self):
        db, exec_mock = _mock_db_chain()
        prodamus = AsyncMock(spec=ProdamusClient)
        prodamus.create_subscription = AsyncMock(return_value=ProdamusSubscriptionResponse(
            payment_link="https://pay.test/lnk",
            order_id="ord-1",
            status="pending",
        ))
        svc = SubscriptionService(db_client=db, prodamus=prodamus)
        req = CreateSubscriptionRequest(
            user_id="user-1",
            tier=SubscriptionTier.pro,
        )
        resp = await svc.create_subscription(req)
        assert resp.status == "pending"
        assert resp.payment_url == "https://pay.test/lnk"
        prodamus.create_subscription.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_paid_subscription_prodamus_fails(self):
        db, exec_mock = _mock_db_chain()
        prodamus = AsyncMock(spec=ProdamusClient)
        prodamus.create_subscription = AsyncMock(side_effect=RuntimeError("API down"))
        svc = SubscriptionService(db_client=db, prodamus=prodamus)
        req = CreateSubscriptionRequest(
            user_id="user-1",
            tier=SubscriptionTier.pro,
        )
        resp = await svc.create_subscription(req)
        assert resp.status == "pending"
        assert resp.payment_url is None


# ── SubscriptionService.handle_webhook ─────────────────────────────────────

class TestHandleWebhook:
    @pytest.mark.asyncio
    async def test_webhook_success(self):
        row = {
            "id": "sub-w1",
            "user_id": "user-1",
            "tier": "pro",
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        db, exec_mock = _mock_db_chain(return_data=[row])
        svc = SubscriptionService(db_client=db)
        payload = ProdamusWebhookPayload(
            order_num="sub-w1",
            payment_status="success",
            amount=990.0,
            currency="RUB",
        )
        result = await svc.handle_webhook(payload)
        assert result is True
        # update should have been called on subscriptions
        update_calls = db.table.return_value.update.call_args_list
        assert len(update_calls) >= 2  # subscription update + transaction update

    @pytest.mark.asyncio
    async def test_webhook_failed(self):
        row = {
            "id": "sub-w2",
            "user_id": "user-1",
            "tier": "pro",
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        db, _ = _mock_db_chain(return_data=[row])
        svc = SubscriptionService(db_client=db)
        payload = ProdamusWebhookPayload(
            order_num="sub-w2",
            payment_status="failed",
            amount=990.0,
        )
        result = await svc.handle_webhook(payload)
        assert result is True
        # subscription should be marked failed
        update_calls = db.table.return_value.update.call_args_list
        assert len(update_calls) >= 2

    @pytest.mark.asyncio
    async def test_webhook_missing_order_id(self):
        db, _ = _mock_db_chain()
        svc = SubscriptionService(db_client=db)
        payload = ProdamusWebhookPayload(
            payment_status="success",
            amount=990.0,
        )
        result = await svc.handle_webhook(payload)
        assert result is False

    @pytest.mark.asyncio
    async def test_webhook_subscription_not_found(self):
        db, _ = _mock_db_chain(return_data=[])  # no match
        svc = SubscriptionService(db_client=db)
        payload = ProdamusWebhookPayload(
            order_num="nonexistent",
            payment_status="success",
            amount=990.0,
        )
        result = await svc.handle_webhook(payload)
        assert result is False


# ── verify_prodamus_signature standalone ──────────────────────────────────

class TestVerifyProdamusSignature:
    def test_valid_signature(self):
        secret = "standalone-key"
        body = b"payload"
        sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        assert verify_prodamus_signature(body, sig, secret) is True

    def test_invalid_signature(self):
        secret = "standalone-key"
        body = b"payload"
        assert verify_prodamus_signature(body, "badsig", secret) is False
