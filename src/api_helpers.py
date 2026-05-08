"""Shared helpers for all API routers."""

import json
from datetime import datetime, timezone
from fastapi import HTTPException

# ── In-memory interview sessions ──
active_interviews: dict[str, dict] = {}

# ── Rate limiter (naive in-memory dict) ──
_rate_limit_store: dict[str, tuple[int, datetime]] = {}

def rate_limit_check(key: str, max_requests: int = 5, window_seconds: int = 60):
    """Naive per-process in-memory rate limiter. Not shared across workers/processes."""
    now = datetime.now(timezone.utc)
    count, first = _rate_limit_store.get(key, (0, now))
    if (now - first).total_seconds() > window_seconds:
        count, first = 0, now
    count += 1
    _rate_limit_store[key] = (count, first)
    if count > max_requests:
        raise HTTPException(status_code=429, detail="Слишком много запросов. Попробуйте позже.")


def _to_expert_card_response(row: dict) -> dict:
    if not row:
        return {}
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "nickname": row.get("nickname"),
        "age": row.get("age"),
        "profession": row.get("profession"),
        "city": row.get("city"),
        "email": row.get("data_subject_email"),
        "phone": row.get("data_subject_phone"),
        "expertise": json.loads(row.get("expertise", "[]") or "[]"),
        "uvp": row.get("uvp"),
        "consent_granted": row.get("consent_granted"),
        "consent_granted_at": row.get("consent_granted_at"),
        "is_anonymized": row.get("is_anonymized"),
        "retention_until": row.get("retention_until"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _filter_fields_for_user(row: dict, user: dict) -> dict:
    """Strip sensitive PDn fields from expert row unless user is owner or admin."""
    resp = dict(row)
    is_owner = (resp.get("owner_user_id") == user.get("id"))
    is_admin = (user.get("role") == "admin")
    if not (is_owner or is_admin):
        resp.pop("data_subject_email", None)
        resp.pop("data_subject_phone", None)
    return resp
