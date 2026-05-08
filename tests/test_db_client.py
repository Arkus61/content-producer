"""Tests for SupabaseDB — in-memory mode (no Supabase URL)."""

import pytest
import json
from src.db_client import db, _mem, _InMemoryStore


@pytest.fixture(autouse=True)
def reset_memory():
    """Reset in-memory store before each test."""
    _mem.__init__()
    yield
    _mem.__init__()


# ── InMemoryStore Unit Tests ─────────────────────────────────

class TestInMemoryStore:
    @pytest.mark.asyncio
    async def test_insert_adds_row_with_id(self):
        row = await _mem._insert("users", {"name": "Alice"})
        assert "id" in row
        assert row["name"] == "Alice"
        assert "created_at" in row

    @pytest.mark.asyncio
    async def test_insert_preserves_given_id(self):
        row = await _mem._insert("users", {"id": "uid-1", "name": "Bob"})
        assert row["id"] == "uid-1"

    @pytest.mark.asyncio
    async def test_select_all_returns_rows(self):
        await _mem._insert("users", {"name": "A"})
        await _mem._insert("users", {"name": "B"})
        rows = await _mem._select_all("users")
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_select_all_filters(self):
        await _mem._insert("users", {"name": "A", "role": "admin"})
        await _mem._insert("users", {"name": "B", "role": "operator"})
        rows = await _mem._select_all("users", role="admin")
        assert len(rows) == 1
        assert rows[0]["name"] == "A"

    @pytest.mark.asyncio
    async def test_select_one_found(self):
        row = await _mem._insert("users", {"id": "uid-1", "name": "A"})
        found = await _mem._select_one("users", "uid-1")
        assert found == row

    @pytest.mark.asyncio
    async def test_select_one_not_found(self):
        found = await _mem._select_one("users", "nonexistent")
        assert found is None

    @pytest.mark.asyncio
    async def test_update_modifies_row(self):
        row = await _mem._insert("users", {"id": "uid-1", "name": "Old"})
        updated = await _mem._update("users", "uid-1", {"name": "New"})
        assert updated["name"] == "New"
        assert "updated_at" in updated

    @pytest.mark.asyncio
    async def test_update_raises_on_missing(self):
        with pytest.raises(ValueError):
            await _mem._update("users", "nonexistent", {"name": "X"})

    @pytest.mark.asyncio
    async def test_delete_removes_row(self):
        await _mem._insert("users", {"id": "uid-1"})
        await _mem._delete("users", "uid-1")
        assert await _mem._select_one("users", "uid-1") is None


# ── SupabaseDB Expert Card Tests ────────────────────────────

class TestExpertCard:
    @pytest.mark.asyncio
    async def test_insert_and_get_expert(self):
        data = {"id": "exp-1", "name": "Эксперт 1", "profession": "Маркетолог", "expertise": ["SMM", "SEO"]}
        await db.expert_insert(data)
        expert = await db.expert_get("exp-1")
        assert expert is not None
        assert expert["name"] == "Эксперт 1"
        assert json.loads(expert["expertise"]) == ["SMM", "SEO"]

    @pytest.mark.asyncio
    async def test_list_experts(self):
        await db.expert_insert({"id": "exp-1", "name": "A"})
        await db.expert_insert({"id": "exp-2", "name": "B"})
        experts = await db.expert_list()
        assert len(experts) == 2

    @pytest.mark.asyncio
    async def test_list_experts_with_owner_filter(self):
        await db.expert_insert({"id": "exp-1", "name": "A", "owner_user_id": "user-1"})
        await db.expert_insert({"id": "exp-2", "name": "B", "owner_user_id": "user-2"})
        experts = await db.expert_list(owner_user_id="user-1")
        assert len(experts) == 1
        assert experts[0]["id"] == "exp-1"

    @pytest.mark.asyncio
    async def test_list_experts_pagination(self):
        for i in range(10):
            await db.expert_insert({"id": f"exp-{i}", "name": f"Expert {i}"})
        page1 = await db.expert_list(skip=0, limit=3)
        page2 = await db.expert_list(skip=3, limit=3)
        assert len(page1) == 3
        assert len(page2) == 3
        assert page1[0]["id"] != page2[0]["id"]

    @pytest.mark.asyncio
    async def test_update_expert(self):
        await db.expert_insert({"id": "exp-1", "name": "Old"})
        await db.expert_update("exp-1", {"name": "New", "city": "Moscow"})
        expert = await db.expert_get("exp-1")
        assert expert["name"] == "New"
        assert expert["city"] == "Moscow"

    @pytest.mark.asyncio
    async def test_delete_expert(self):
        await db.expert_insert({"id": "exp-1", "name": "ToDelete"})
        result = await db.expert_delete("exp-1")
        assert result is True
        expert = await db.expert_get("exp-1")
        assert expert is None

    @pytest.mark.asyncio
    async def test_serialize_lists_on_insert(self):
        """List fields should be JSON-serialized on insert."""
        await db.expert_insert({"id": "exp-1", "expertise": ["A", "B"], "stories": ["S1"]})
        expert = await db.expert_get("exp-1")
        assert isinstance(expert["expertise"], str)
        assert json.loads(expert["expertise"]) == ["A", "B"]


# ── SupabaseDB User Tests ───────────────────────────────────

class TestUsers:
    @pytest.mark.asyncio
    async def test_user_create(self):
        user = await db.user_create({"supabase_uid": "suid-1", "email": "a@b.com", "full_name": "Alice"})
        assert user["supabase_uid"] == "suid-1"
        assert user["email"] == "a@b.com"

    @pytest.mark.asyncio
    async def test_user_get_by_supabase_uid(self):
        await db.user_create({"supabase_uid": "suid-1", "email": "a@b.com"})
        user = await db.user_get_by_supabase_uid("suid-1")
        assert user is not None
        assert user["email"] == "a@b.com"

    @pytest.mark.asyncio
    async def test_user_get_by_supabase_uid_not_found(self):
        user = await db.user_get_by_supabase_uid("nonexistent")
        assert user is None

    @pytest.mark.asyncio
    async def test_user_update(self):
        await db.user_create({"id": "u-1", "supabase_uid": "suid-1", "email": "old@b.com"})
        updated = await db.user_update("u-1", {"email": "new@b.com", "full_name": "Bob"})
        assert updated["email"] == "new@b.com"
        assert updated["full_name"] == "Bob"

    @pytest.mark.asyncio
    async def test_user_set_last_login(self):
        user = await db.user_create({"id": "u-1", "supabase_uid": "suid-1"})
        assert "last_login_at" not in user
        await db.user_set_last_login("u-1")
        found = await db.user_get_by_supabase_uid("suid-1")
        assert "last_login_at" in found


# ── SupabaseDB Consent Tests ─────────────────────────────────

class TestConsent:
    @pytest.mark.asyncio
    async def test_consent_insert(self):
        log = await db.consent_insert({
            "id": "c-1", "expert_id": "exp-1", "consent_type": "processing",
            "is_granted": True, "consent_version": "1.0"
        })
        assert log["id"] == "c-1"
        assert log["expert_id"] == "exp-1"

    @pytest.mark.asyncio
    async def test_consent_list(self):
        for ctype in ("processing", "marketing"):
            await db.consent_insert({
                "expert_id": "exp-1", "consent_type": ctype,
                "is_granted": True, "consent_version": "1.0"
            })
        logs = await db.consent_list("exp-1")
        assert len(logs) == 2

    @pytest.mark.asyncio
    async def test_consent_withdraw(self):
        await db.consent_insert({
            "expert_id": "exp-1", "consent_type": "processing",
            "is_granted": True, "consent_version": "1.0"
        })
        await db.consent_withdraw("exp-1", "processing")
        logs = await db.consent_list("exp-1")
        assert "withdraw_at" in logs[0]


# ── SupabaseDB Audit Tests ──────────────────────────────────

class TestAudit:
    @pytest.mark.asyncio
    async def test_audit_insert(self):
        entry = await db.audit_insert({
            "table_name": "experts", "record_id": "exp-1", "action": "create"
        })
        assert entry["table_name"] == "experts"
        assert entry["action"] == "create"

    @pytest.mark.asyncio
    async def test_audit_ip_anonymization(self):
        """IP should be anonymized to first 2 octets."""
        entry = await db.audit_insert({
            "table_name": "x", "record_id": "r-1", "action": "view",
            "ip_address": "192.168.1.100"
        })
        assert entry["ip_address"] == "192.168.*.*"

    @pytest.mark.asyncio
    async def test_audit_list(self):
        await db.audit_insert({"table_name": "a", "record_id": "r-1", "action": "create"})
        await db.audit_insert({"table_name": "b", "record_id": "r-2", "action": "update"})
        count, rows = await db.audit_list()
        assert count == 2
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_audit_list_with_filter(self):
        await db.audit_insert({"table_name": "a", "record_id": "r-1", "action": "create"})
        await db.audit_insert({"table_name": "b", "record_id": "r-2", "action": "update"})
        count, rows = await db.audit_list(table_name="a")
        assert count == 1
        assert rows[0]["table_name"] == "a"


# ── SupabaseDB Export Tests ─────────────────────────────────

class TestExport:
    @pytest.mark.asyncio
    async def test_export_insert(self):
        log = await db.export_insert({
            "id": "e-1", "expert_id": "exp-1",
            "export_format": "json", "status": "processing"
        })
        assert log["id"] == "e-1"
        assert log["export_format"] == "json"

    @pytest.mark.asyncio
    async def test_export_get(self):
        await db.export_insert({
            "id": "e-1", "expert_id": "exp-1", "status": "processing"
        })
        found = await db.export_get("e-1")
        assert found is not None
        assert found["status"] == "processing"

    @pytest.mark.asyncio
    async def test_export_update(self):
        await db.export_insert({
            "id": "e-1", "expert_id": "exp-1", "status": "processing"
        })
        updated = await db.export_update("e-1", {
            "status": "ready", "file_path": "/tmp/x.json"
        })
        assert updated["status"] == "ready"
        assert updated["file_path"] == "/tmp/x.json"


# ── SupabaseDB Deletion Tests ───────────────────────────────

class TestDeletion:
    @pytest.mark.asyncio
    async def test_deletion_insert(self):
        log = await db.deletion_insert({
            "id": "d-1", "expert_id": "exp-1",
            "reason": "subject_request", "status": "pending"
        })
        assert log["id"] == "d-1"
        assert log["status"] == "pending"

    @pytest.mark.asyncio
    async def test_deletion_get(self):
        await db.deletion_insert({
            "id": "d-1", "expert_id": "exp-1", "status": "pending"
        })
        found = await db.deletion_get("d-1")
        assert found is not None

    @pytest.mark.asyncio
    async def test_deletion_update(self):
        await db.deletion_insert({
            "id": "d-1", "expert_id": "exp-1", "status": "pending"
        })
        updated = await db.deletion_update("d-1", {"status": "completed"})
        assert updated["status"] == "completed"


# ── SupabaseDB Interview Tests ──────────────────────────────

class TestInterview:
    @pytest.mark.asyncio
    async def test_interview_insert(self):
        sess = await db.interview_insert({
            "id": "sess-1", "expert_name": "Test", "responses": "{}"
        })
        assert sess["id"] == "sess-1"
        assert sess["expert_name"] == "Test"

    @pytest.mark.asyncio
    async def test_interview_get(self):
        await db.interview_insert({"id": "sess-1", "expert_name": "Test"})
        found = await db.interview_get("sess-1")
        assert found is not None

    @pytest.mark.asyncio
    async def test_interview_update(self):
        await db.interview_insert({"id": "sess-1", "responses": "{}"})
        updated = await db.interview_update("sess-1", {
            "responses": '{"q1":"a1"}'
        })
        assert updated["responses"] == '{"q1":"a1"}'

    @pytest.mark.asyncio
    async def test_interview_list(self):
        await db.interview_insert({"id": "s-1", "expert_id": "exp-1"})
        await db.interview_insert({"id": "s-2", "expert_id": "exp-1"})
        rows = await db.interview_list("exp-1")
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_interview_delete(self):
        await db.interview_insert({"id": "sess-1"})
        result = await db.interview_delete("sess-1")
        assert result is True
        assert await db.interview_get("sess-1") is None


# ── SupabaseDB Transcription Tests ──────────────────────────

class TestTranscription:
    @pytest.mark.asyncio
    async def test_transcription_insert(self):
        t = await db.transcription_insert({
            "id": "t-1", "expert_id": "exp-1",
            "source_url": "https://youtube.com", "text": "Hello"
        })
        assert t["id"] == "t-1"
        assert t["text"] == "Hello"

    @pytest.mark.asyncio
    async def test_transcription_get(self):
        await db.transcription_insert({
            "id": "t-1", "expert_id": "exp-1", "text": "Hello"
        })
        found = await db.transcription_get("t-1")
        assert found is not None

    @pytest.mark.asyncio
    async def test_transcription_list_by_expert(self):
        await db.transcription_insert({
            "id": "t-1", "expert_id": "exp-1", "text": "A"
        })
        await db.transcription_insert({
            "id": "t-2", "expert_id": "exp-2", "text": "B"
        })
        rows = await db.transcription_list(expert_id="exp-1")
        assert len(rows) == 1
        assert rows[0]["id"] == "t-1"

    @pytest.mark.asyncio
    async def test_transcription_list_by_creator(self):
        await db.transcription_insert({
            "id": "t-1", "expert_id": "exp-1",
            "creator_user_id": "user-1", "text": "A"
        })
        await db.transcription_insert({
            "id": "t-2", "expert_id": "exp-1",
            "creator_user_id": "user-2", "text": "B"
        })
        rows = await db.transcription_list(creator_user_id="user-1")
        assert len(rows) == 1
        assert rows[0]["id"] == "t-1"

    @pytest.mark.asyncio
    async def test_transcription_delete(self):
        await db.transcription_insert({"id": "t-1"})
        result = await db.transcription_delete("t-1")
        assert result is True
        assert await db.transcription_get("t-1") is None


# ── SupabaseDB Content Tests ────────────────────────────────

class TestContent:
    @pytest.mark.asyncio
    async def test_content_insert(self):
        c = await db.content_insert({
            "id": "c-1", "expert_id": "exp-1",
            "content_type": "post", "body": "Hello world",
            "platform": "telegram"
        })
        assert c["id"] == "c-1"
        assert c["platform"] == "telegram"

    @pytest.mark.asyncio
    async def test_content_list(self):
        await db.content_insert({"id": "c-1", "expert_id": "exp-1"})
        await db.content_insert({"id": "c-2", "expert_id": "exp-1"})
        rows = await db.content_list("exp-1")
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_content_list_pagination(self):
        for i in range(5):
            await db.content_insert({"id": f"c-{i}", "expert_id": "exp-1"})
        page = await db.content_list("exp-1", skip=0, limit=2)
        assert len(page) == 2

    @pytest.mark.asyncio
    async def test_content_delete(self):
        await db.content_insert({"id": "c-1", "expert_id": "exp-1"})
        result = await db.content_delete("c-1")
        assert result is True


# ── SupabaseDB Storage Tests ────────────────────────────────

class TestStorage:
    @pytest.mark.asyncio
    async def test_storage_upload(self):
        path = await db.storage_upload(
            "exports", "test.json", b'{"a": 1}', "application/json"
        )
        assert path == "test.json"
        assert _mem.tables["exports"]["test.json"] == b'{"a": 1}'

    @pytest.mark.asyncio
    async def test_storage_get_url(self):
        await db.storage_upload("exports", "test.json", b"data")
        url = await db.storage_get_url("exports", "test.json")
        assert url == "memory://exports/test.json"
