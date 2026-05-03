"""
Supabase DB client — async CRUD with in-memory fallback for tests.

When SUPABASE_URL is set → real Supabase PostgreSQL.
When empty → lightweight async in-memory dict (for tests / local dev).
"""
import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from .supabase_client import supabase_client
from .config import settings


class _InMemoryStore:
    """Async-compatible in-memory store for local testing."""
    def __init__(self):
        self.tables = {name: {} for name in [
            "expert_cards", "users", "consent_logs", "audit_logs",
            "data_export_logs", "data_deletion_logs", "interview_sessions",
            "transcriptions", "content_items"
        ]}

    async def _insert(self, table: str, data: dict) -> dict:
        d = dict(data)
        d.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        if "id" not in d:
            d["id"] = str(uuid.uuid4())
        self.tables[table][d["id"]] = d
        return d

    async def _select_all(self, table: str, **filters) -> List[dict]:
        rows = list(self.tables[table].values())
        for k, v in filters.items():
            rows = [r for r in rows if r.get(k) == v]
        # Sort by created_at desc
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return rows

    async def _select_one(self, table: str, row_id: str) -> Optional[dict]:
        return self.tables[table].get(row_id)

    async def _update(self, table: str, row_id: str, data: dict) -> dict:
        if row_id in self.tables[table]:
            self.tables[table][row_id].update(data)
            self.tables[table][row_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            return self.tables[table][row_id]
        raise ValueError(f"Row {row_id} not found in {table}")

    async def _delete(self, table: str, row_id: str) -> None:
        self.tables[table].pop(row_id, None)


_mem = _InMemoryStore()


class SupabaseDB:
    """Async CRUD — Supabase when configured, in-memory otherwise."""

    # ── Expert Cards ──────────────────────────────────────
    async def expert_list(self, skip: int = 0, limit: int = 50, owner_user_id: Optional[str] = None) -> List[dict]:
        if settings.supabase_url:
            query = supabase_client.table("expert_cards").select("*").order("created_at", desc=True)
            if owner_user_id:
                query = query.eq("owner_user_id", owner_user_id)
            result = await query.range(skip, skip + limit - 1).execute()
            return result.data or []
        rows = await _mem._select_all("expert_cards")
        if owner_user_id:
            rows = [r for r in rows if r.get("owner_user_id") == owner_user_id]
        return rows[skip: skip + limit]

    async def expert_get(self, expert_id: str) -> Optional[dict]:
        if settings.supabase_url:
            result = await supabase_client.table("expert_cards").select("*").eq("id", expert_id).single().execute()
            return result.data
        return await _mem._select_one("expert_cards", expert_id)

    @staticmethod
    def _serialize_lists(data: dict) -> None:
        for field in [
            "expertise", "stories", "achievements", "audience_pains",
            "strategy_goals", "strategy_platforms", "style_vocabulary",
        ]:
            if field in data and isinstance(data[field], list):
                data[field] = json.dumps(data[field])

    async def expert_insert(self, data: dict) -> dict:
        self._serialize_lists(data)
        if settings.supabase_url:
            result = await supabase_client.table("expert_cards").insert(data).execute()
            return result.data[0] if result.data else data
        return await _mem._insert("expert_cards", data)

    async def expert_update(self, expert_id: str, data: dict) -> dict:
        self._serialize_lists(data)
        data.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
        if settings.supabase_url:
            result = await supabase_client.table("expert_cards").update(data).eq("id", expert_id).execute()
            return result.data[0] if result.data else data
        return await _mem._update("expert_cards", expert_id, data)

    async def expert_delete(self, expert_id: str) -> bool:
        if settings.supabase_url:
            await supabase_client.table("expert_cards").delete().eq("id", expert_id).execute()
            return True
        await _mem._delete("expert_cards", expert_id)
        return True

    # ── Users ─────────────────────────────────────────────
    async def user_get_by_supabase_uid(self, uid: str) -> Optional[dict]:
        if settings.supabase_url:
            result = await supabase_client.table("users").select("*").eq("supabase_uid", uid).limit(1).execute()
            return result.data[0] if result.data else None
        rows = await _mem._select_all("users")
        for r in rows:
            if r.get("supabase_uid") == uid:
                return r
        return None

    async def user_create(self, data: dict) -> dict:
        if settings.supabase_url:
            result = await supabase_client.table("users").insert(data).execute()
            return result.data[0] if result.data else data
        return await _mem._insert("users", data)

    async def user_update(self, user_id: str, data: dict) -> dict:
        if settings.supabase_url:
            result = await supabase_client.table("users").update(data).eq("id", user_id).execute()
            return result.data[0] if result.data else data
        return await _mem._update("users", user_id, data)

    async def user_set_last_login(self, user_id: str) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        if settings.supabase_url:
            await supabase_client.table("users").update({"last_login_at": ts}).eq("id", user_id).execute()
        else:
            if user_id in _mem.tables["users"]:
                _mem.tables["users"][user_id]["last_login_at"] = ts

    # ── Consent Logs ──────────────────────────────────────
    async def consent_insert(self, data: dict) -> dict:
        if settings.supabase_url:
            result = await supabase_client.table("consent_logs").insert(data).execute()
            return result.data[0] if result.data else data
        return await _mem._insert("consent_logs", data)

    async def consent_list(self, expert_id: str) -> List[dict]:
        if settings.supabase_url:
            result = await supabase_client.table("consent_logs").select("*").eq("expert_id", expert_id).order("granted_at", desc=True).execute()
            return result.data or []
        rows = await _mem._select_all("consent_logs", expert_id=expert_id)
        return rows

    async def consent_withdraw(self, expert_id: str, consent_type: str) -> None:
        if settings.supabase_url:
            await supabase_client.table("consent_logs").update({"withdraw_at": datetime.now(timezone.utc).isoformat()}) \
                .eq("expert_id", expert_id).eq("consent_type", consent_type).execute()
            await supabase_client.table("expert_cards").update({"consent_granted": False}).eq("id", expert_id).execute()
        else:
            # Update consent
            for row in _mem.tables["consent_logs"].values():
                if row.get("expert_id") == expert_id and row.get("consent_type") == consent_type:
                    row["withdraw_at"] = datetime.now(timezone.utc).isoformat()
            # Update expert
            if expert_id in _mem.tables["expert_cards"]:
                _mem.tables["expert_cards"][expert_id]["consent_granted"] = False

    # ── Audit Logs ────────────────────────────────────────
    async def audit_insert(self, data: dict) -> dict:
        if data.get("ip_address") and settings.anonymize_audit_ips:
            parts = data["ip_address"].split(".")
            if len(parts) == 4:
                data["ip_address"] = f"{parts[0]}.{parts[1]}.*.*"
        if settings.supabase_url:
            result = await supabase_client.table("audit_logs").insert(data).execute()
            return result.data[0] if result.data else data
        return await _mem._insert("audit_logs", data)

    async def audit_list(self, limit: int = 100, skip: int = 0, **filters) -> tuple[int, List[dict]]:
        if settings.supabase_url:
            query = supabase_client.table("audit_logs").select("*", count="exact")
            for k, v in filters.items():
                if v: query = query.eq(k, v)
            result = await query.order("created_at", desc=True).range(skip, skip + limit - 1).execute()
            return result.count or 0, result.data or []
        rows = list(_mem.tables["audit_logs"].values())
        for k, v in filters.items():
            if v: rows = [r for r in rows if r.get(k) == v]
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return len(rows), rows[skip: skip + limit]

    # ── Export Logs ───────────────────────────────────────
    async def export_insert(self, data: dict) -> dict:
        if settings.supabase_url:
            result = await supabase_client.table("data_export_logs").insert(data).execute()
            return result.data[0] if result.data else data
        return await _mem._insert("data_export_logs", data)

    async def export_get(self, request_id: str) -> Optional[dict]:
        if settings.supabase_url:
            result = await supabase_client.table("data_export_logs").select("*").eq("id", request_id).single().execute()
            return result.data
        return await _mem._select_one("data_export_logs", request_id)

    async def export_update(self, request_id: str, data: dict) -> dict:
        if settings.supabase_url:
            result = await supabase_client.table("data_export_logs").update(data).eq("id", request_id).execute()
            return result.data[0] if result.data else data
        return await _mem._update("data_export_logs", request_id, data)

    # ── Deletion Logs ─────────────────────────────────────
    async def deletion_insert(self, data: dict) -> dict:
        if settings.supabase_url:
            result = await supabase_client.table("data_deletion_logs").insert(data).execute()
            return result.data[0] if result.data else data
        return await _mem._insert("data_deletion_logs", data)

    async def deletion_get(self, request_id: str) -> Optional[dict]:
        if settings.supabase_url:
            result = await supabase_client.table("data_deletion_logs").select("*").eq("id", request_id).single().execute()
            return result.data
        return await _mem._select_one("data_deletion_logs", request_id)

    async def deletion_update(self, request_id: str, data: dict) -> dict:
        if settings.supabase_url:
            result = await supabase_client.table("data_deletion_logs").update(data).eq("id", request_id).execute()
            return result.data[0] if result.data else data
        return await _mem._update("data_deletion_logs", request_id, data)

    # ── Interview Sessions (in-memory + optional DB) ────────
    async def interview_insert(self, data: dict) -> dict:
        if settings.supabase_url:
            result = await supabase_client.table("interview_sessions").insert(data).execute()
            return result.data[0] if result.data else data
        return await _mem._insert("interview_sessions", data)

    async def interview_get(self, session_id: str) -> Optional[dict]:
        if settings.supabase_url:
            result = await supabase_client.table("interview_sessions").select("*").eq("id", session_id).single().execute()
            return result.data
        return await _mem._select_one("interview_sessions", session_id)

    async def interview_update(self, session_id: str, data: dict) -> dict:
        if settings.supabase_url:
            result = await supabase_client.table("interview_sessions").update(data).eq("id", session_id).execute()
            return result.data[0] if result.data else data
        return await _mem._update("interview_sessions", session_id, data)

    async def interview_list(self, expert_id: str) -> List[dict]:
        if settings.supabase_url:
            result = await supabase_client.table("interview_sessions").select("*").eq("expert_id", expert_id).execute()
            return result.data or []
        rows = await _mem._select_all("interview_sessions", expert_id=expert_id)
        return rows

    async def interview_delete(self, session_id: str) -> bool:
        if settings.supabase_url:
            await supabase_client.table("interview_sessions").delete().eq("id", session_id).execute()
            return True
        await _mem._delete("interview_sessions", session_id)
        return True

    # ── Transcriptions ─────────────────────────────────────
    async def transcription_insert(self, data: dict) -> dict:
        if settings.supabase_url:
            result = await supabase_client.table("transcriptions").insert(data).execute()
            return result.data[0] if result.data else data
        return await _mem._insert("transcriptions", data)

    async def transcription_list(self, expert_id: str | None = None, creator_user_id: str | None = None) -> List[dict]:
        if settings.supabase_url:
            query = supabase_client.table("transcriptions").select("*")
            if expert_id is not None:
                query = query.eq("expert_id", expert_id)
            if creator_user_id is not None:
                query = query.eq("creator_user_id", creator_user_id)
            if expert_id is None and creator_user_id is None:
                pass
            result = await query.execute()
            return result.data or []
        rows = await _mem._select_all("transcriptions")
        if expert_id is not None:
            rows = [r for r in rows if r.get("expert_id") == expert_id]
        if creator_user_id is not None:
            rows = [r for r in rows if r.get("creator_user_id") == creator_user_id]
        return rows

    async def transcription_get(self, transcription_id: str) -> Optional[dict]:
        if settings.supabase_url:
            result = await supabase_client.table("transcriptions").select("*").eq("id", transcription_id).single().execute()
            return result.data
        return await _mem._select_one("transcriptions", transcription_id)

    async def transcription_delete(self, transcription_id: str) -> bool:
        if settings.supabase_url:
            await supabase_client.table("transcriptions").delete().eq("id", transcription_id).execute()
            return True
        await _mem._delete("transcriptions", transcription_id)
        return True

    # ── Content Items ──────────────────────────────────────
    async def content_insert(self, data: dict) -> dict:
        if settings.supabase_url:
            result = await supabase_client.table("content_items").insert(data).execute()
            return result.data[0] if result.data else data
        return await _mem._insert("content_items", data)

    async def content_list(self, expert_id: str, skip: int = 0, limit: int = 20) -> List[dict]:
        if settings.supabase_url:
            result = await supabase_client.table("content_items").select("*") \
                .eq("expert_id", expert_id).order("created_at", desc=True).range(skip, skip + limit - 1).execute()
            return result.data or []
        rows = await _mem._select_all("content_items", expert_id=expert_id)
        return rows[skip: skip + limit]

    async def content_delete(self, content_id: str) -> bool:
        if settings.supabase_url:
            await supabase_client.table("content_items").delete().eq("id", content_id).execute()
            return True
        await _mem._delete("content_items", content_id)
        return True

    # ── Storage (Supabase Storage) ──────────────────────────
    async def storage_upload(self, bucket: str, path: str, file_bytes: bytes, content_type: str = "application/octet-stream") -> str:
        if settings.supabase_url:
            result = await supabase_client.storage.from_(bucket).upload(path, file_bytes, {"content-type": content_type})
            return result.data["Key"] if hasattr(result, "data") and result.data else path
        # In-memory fallback — store in a "bucket" dict
        if bucket not in _mem.tables:
            _mem.tables[bucket] = {}
        _mem.tables[bucket][path] = file_bytes
        return path

    async def storage_get_url(self, bucket: str, path: str, ttl: int = 3600) -> str:
        if settings.supabase_url:
            result = await supabase_client.storage.from_(bucket).create_signed_url(path, ttl)
            return result.data["signedURL"] if hasattr(result, "data") and result.data else ""
        return f"memory://{bucket}/{path}"


# Global instance
db = SupabaseDB()
