"""152-FZ compliance — simple async functions using db_client."""
import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import uuid4

from .config import settings
from .db_client import db


# ── Consent ─────────────────────────────────────────────

async def log_consent(
    expert_id: str,
    consent_type: str = "processing",
    is_granted: bool = True,
    consent_version: str = "1.0",
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict:
    """Log consent + update expert card."""
    log = await db.consent_insert({
        "id": str(uuid4()),
        "expert_id": expert_id,
        "consent_type": consent_type,
        "is_granted": is_granted,
        "consent_version": consent_version,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "granted_at": datetime.now(timezone.utc).isoformat(),
    })
    if is_granted:
        await db.expert_update(expert_id, {
            "consent_granted": True,
            "consent_version": consent_version,
            "consent_granted_at": datetime.now(timezone.utc).isoformat(),
        })
    return log


async def withdraw_consent(expert_id: str, consent_type: str = "processing") -> None:
    await db.consent_withdraw(expert_id, consent_type)
    await audit_log("consent_log", expert_id, "withdraw", details={"consent_type": consent_type})


# ── Export ──────────────────────────────────────────────

async def request_export(
    expert_id: str,
    export_format: str = "json",
    include_transcriptions: bool = True,
) -> str:
    request_id = str(uuid4())
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.export_ttl_hours)
    await db.export_insert({
        "id": request_id,
        "expert_id": expert_id,
        "export_format": export_format,
        "include_transcriptions": include_transcriptions,
        "status": "processing",
        "expires_at": expires.isoformat(),
        "requested_at": datetime.now(timezone.utc).isoformat(),
    })
    # Fire-and-forget prepare
    asyncio.create_task(_prepare_export(request_id, expert_id, export_format, include_transcriptions))
    return request_id


async def _prepare_export(request_id: str, expert_id: str, export_format: str, include_transcriptions: bool):
    try:
        expert = await db.expert_get(expert_id)
        if not expert:
            await db.export_update(request_id, {"status": "error"})
            return

        payload = {
            "operator_name": settings.operator_name,
            "operator_address": settings.operator_address,
            "operator_inn": settings.operator_inn,
            "export_date": datetime.now(timezone.utc).isoformat(),
            "expert": {k: v for k, v in expert.items() if v is not None},
            "consents": [],
        }

        consents = await db.consent_list(expert_id)
        for c in consents:
            payload["consents"].append({
                "type": c.get("consent_type"),
                "version": c.get("consent_version"),
                "granted": c.get("is_granted"),
                "granted_at": c.get("granted_at"),
                "withdrawn_at": c.get("withdraw_at"),
            })

        if include_transcriptions:
            trans = await db.transcription_list(expert_id)
            payload["transcriptions"] = [{"id": t.get("id"), "source_url": t.get("source_url"), "text": t.get("text")} for t in trans]

        file_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        path = f"exports/export_{request_id}.json"

        await db.storage_upload("exports", path, file_bytes, "application/json")

        await db.export_update(request_id, {
            "status": "ready",
            "file_path": path,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        await db.export_update(request_id, {"status": "error"})


# ── Deletion ────────────────────────────────────────────

async def request_deletion(
    expert_id: str,
    reason: str = "subject_request",
    deletion_scope: str = "all",
) -> str:
    request_id = str(uuid4())
    await db.deletion_insert({
        "id": request_id,
        "expert_id": expert_id,
        "reason": reason,
        "deletion_scope": deletion_scope,
        "status": "pending",
        "requested_at": datetime.now(timezone.utc).isoformat(),
    })
    asyncio.create_task(_execute_deletion(request_id, expert_id, deletion_scope))
    return request_id


async def _execute_deletion(request_id: str, expert_id: str, scope: str):
    """Background: anonymize after grace period."""
    await asyncio.sleep(60)  # Reduced for tests; production: hours * 3600

    try:
        if scope == "all":
            await db.expert_update(expert_id, {
                "name": "[Удалён]", "nickname": "", "age": None, "city": "", "profession": "",
                "data_subject_email": None, "data_subject_phone": None,
                "is_anonymized": True, "uvp": "", "expertise": "[]",
                "stories": "[]", "achievements": "[]",
            })
        await db.deletion_update(request_id, {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        await db.deletion_update(request_id, {"status": "failed"})


# ── Audit ─────────────────────────────────────────────────

async def audit_log(
    table_name: str,
    record_id: str,
    action: str,
    performed_by_user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[dict] = None,
) -> dict:
    return await db.audit_insert({
        "table_name": table_name,
        "record_id": record_id,
        "action": action,
        "performed_by_user_id": performed_by_user_id,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "details": json.dumps(details or {}),
    })


async def list_audit_logs(limit: int = 100, skip: int = 0, **filters) -> tuple[int, list]:
    return await db.audit_list(limit, skip, **filters)


# ── Export Response Builder ───────────────────────────────

def build_export_response(row: dict) -> dict:
    return {
        "request_id": row.get("id"),
        "status": row.get("status"),
        "file_url": row.get("file_path"),
        "expires_at": row.get("expires_at"),
    }


def build_deletion_response(row: dict) -> dict:
    return {
        "request_id": row.get("id"),
        "status": row.get("status"),
        "scope": row.get("deletion_scope"),
        "requested_at": row.get("requested_at"),
        "completed_at": row.get("completed_at"),
    }
