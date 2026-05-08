"""Tests for compliance module — 152-FZ: consent, export, deletion, audit."""

import pytest
import json
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone

from src.compliance import (
    log_consent,
    withdraw_consent,
    request_export,
    _prepare_export,
    request_deletion,
    _execute_deletion,
    audit_log,
    list_audit_logs,
    build_export_response,
    build_deletion_response,
)
from src.db_client import db, _mem


@pytest.fixture(autouse=True)
def reset_memory():
    _mem.__init__()
    yield
    _mem.__init__()


# ── Consent ─────────────────────────────────────────────────

class TestConsent:
    @pytest.mark.asyncio
    async def test_log_consent_inserts_and_updates_expert(self):
        await db.expert_insert({"id": "exp-1", "name": "Test", "consent_granted": False})

        log = await log_consent("exp-1", "processing", True, "2.0", "1.2.3.4", "UA")
        assert log["expert_id"] == "exp-1"
        assert log["consent_type"] == "processing"
        assert log["is_granted"] is True
        assert log["consent_version"] == "2.0"

        expert = await db.expert_get("exp-1")
        assert expert["consent_granted"] is True
        assert expert["consent_version"] == "2.0"
        assert "consent_granted_at" in expert

    @pytest.mark.asyncio
    async def test_withdraw_consent(self):
        await db.expert_insert({"id": "exp-1", "name": "Test", "consent_granted": False})
        await log_consent("exp-1", "processing", True, "1.0")
        await withdraw_consent("exp-1", "processing")

        logs = await db.consent_list("exp-1")
        assert logs[0]["withdraw_at"] is not None

        expert = await db.expert_get("exp-1")
        assert expert["consent_granted"] is False


# ── Export ──────────────────────────────────────────────────

class TestExport:
    @pytest.mark.asyncio
    async def test_request_export_creates_and_starts_prepare(self):
        request_id = await request_export("exp-1", "json", True)
        assert request_id is not None

        entry = await db.export_get(request_id)
        assert entry is not None
        assert entry["status"] in ("processing", "ready")

    @pytest.mark.asyncio
    async def test_prepare_export_builds_payload_and_uploads(self):
        await db.expert_insert({"id": "exp-1", "name": "Alice", "profession": "Dev"})
        await db.consent_insert({
            "expert_id": "exp-1", "consent_type": "processing",
            "is_granted": True, "consent_version": "1.0", "granted_at": "2025-01-01",
        })
        await db.transcription_insert({"id": "t-1", "expert_id": "exp-1", "text": "Hello", "source_url": "http://youtube"})
        await db.export_insert({"id": "req-1", "expert_id": "exp-1", "status": "processing", "requested_at": "2025-01-01", "expires_at": "2025-01-10"})

        await _prepare_export("req-1", "exp-1", "json", True)

        entry = await db.export_get("req-1")
        assert entry["status"] == "ready"
        assert entry["file_path"] is not None
        assert entry["signed_url"] is not None

        # Check that file was uploaded to storage
        assert "exports" in _mem.tables

    @pytest.mark.asyncio
    async def test_prepare_export_sets_error_on_missing_expert(self):
        await db.export_insert({"id": "req-2", "expert_id": "exp-missing", "status": "processing", "requested_at": "2025-01-01", "expires_at": "2025-01-10"})
        await _prepare_export("req-2", "exp-missing", "json", True)

        entry = await db.export_get("req-2")
        assert entry["status"] == "error"


# ── Deletion ────────────────────────────────────────────────

class TestDeletion:
    @pytest.mark.asyncio
    async def test_request_deletion_creates_entry(self):
        request_id = await request_deletion("exp-1", "subject_request", "all")
        assert request_id is not None

        entry = await db.deletion_get(request_id)
        assert entry is not None
        assert entry["reason"] == "subject_request"
        assert entry["status"] in ("pending", "completed")

    @pytest.mark.asyncio
    @patch("src.compliance.settings")
    @patch("src.compliance.asyncio.sleep")
    async def test_execute_deletion_anonymizes_expert(self, mock_sleep, mock_settings):
        mock_sleep.return_value = None  # skip sleep
        mock_settings.debug = False
        await db.expert_insert({"id": "exp-1", "name": "Alice", "city": "Moscow", "profession": "Dev", "email": "a@b.com"})
        await db.deletion_insert({"id": "d-1", "expert_id": "exp-1", "reason": "test", "status": "pending", "requested_at": datetime.now(timezone.utc).isoformat()})

        await _execute_deletion("d-1", "exp-1", "all")

        expert = await db.expert_get("exp-1")
        assert expert["name"] == "[Удалён]"
        assert expert["is_anonymized"] is True
        assert expert["city"] == ""
        assert expert["data_subject_email"] is None

        entry = await db.deletion_get("d-1")
        assert entry["status"] == "completed"


# ── Audit ───────────────────────────────────────────────────

class TestAuditLog:
    @pytest.mark.asyncio
    async def test_audit_log_inserts_entry(self):
        entry = await audit_log("experts", "exp-1", "create", performed_by_user_id="user-1", ip_address="10.0.0.1")
        assert entry["table_name"] == "experts"
        assert entry["record_id"] == "exp-1"
        assert entry["action"] == "create"

    @pytest.mark.asyncio
    async def test_audit_log_returns_empty_on_failure(self):
        """Should not raise, return empty dict."""
        with patch.object(db, "audit_insert", side_effect=Exception("boom")):
            result = await audit_log("x", "y", "z")
            assert result == {}

    @pytest.mark.asyncio
    async def test_list_audit_logs(self):
        await audit_log("a", "r1", "create")
        await audit_log("b", "r2", "update")
        total, logs = await list_audit_logs()
        assert total == 2
        assert len(logs) == 2

    @pytest.mark.asyncio
    async def test_list_audit_logs_with_filter(self):
        await audit_log("a", "r1", "create")
        await audit_log("b", "r2", "update")
        total, logs = await list_audit_logs(table_name="a")
        assert total == 1


# ── Response builders ───────────────────────────────────────

class TestResponseBuilders:
    def test_build_export_response(self):
        row = {"id": "e-1", "status": "ready", "signed_url": "https://...", "expires_at": "2025-12-31"}
        resp = build_export_response(row)
        assert resp["request_id"] == "e-1"
        assert resp["file_url"] == "https://..."

    def test_build_export_response_fallback_to_path(self):
        row = {"id": "e-2", "status": "ready", "file_path": "/tmp/x.json"}
        resp = build_export_response(row)
        assert resp["file_url"] == "/tmp/x.json"

    def test_build_deletion_response(self):
        row = {"id": "d-1", "status": "completed", "deletion_scope": "all", "requested_at": "2025-01-01", "completed_at": "2025-01-02"}
        resp = build_deletion_response(row)
        assert resp["request_id"] == "d-1"
        assert resp["scope"] == "all"
