"""Expert card CRUD endpoints."""
import uuid
import json
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request
from ..config import settings
from ..db_client import db
from ..db.schemas import ExpertCardCreate, ExpertCardUpdate
from ..dependencies import get_current_user, require_admin, require_expert_owner
from ..compliance import log_consent
from ..api_helpers import _to_expert_card_response, _filter_fields_for_user

router = APIRouter(prefix="/api/experts", tags=["experts"])


@router.get("")
async def list_experts(skip: int = 0, limit: int = 50, user: dict = Depends(get_current_user)):
    if user.get("role") == "admin":
        experts = await db.expert_list(skip, limit)
    else:
        experts = await db.expert_list(skip, limit, owner_user_id=user.get("id"))
    return {"experts": [_to_expert_card_response(_filter_fields_for_user(e, user)) for e in experts]}


@router.get("/{expert_id}")
async def get_expert(expert_id: str, user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)
    return _to_expert_card_response(_filter_fields_for_user(e, user))


@router.post("")
async def create_expert(req: ExpertCardCreate, request: Request, user: dict = Depends(get_current_user)):
    if not req.consent_granted:
        raise HTTPException(status_code=400, detail="Согласие на обработку ПДн обязательно")

    if getattr(req, "consent_version", "") and req.consent_version < settings.minimum_consent_version:
        raise HTTPException(status_code=400, detail=f"Consent version must be >= {settings.minimum_consent_version}")

    expert_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    retention = (datetime.now(timezone.utc) + timedelta(days=settings.default_retention_days)).isoformat()

    data = {
        "id": expert_id, "name": req.name, "nickname": req.nickname,
        "age": req.age, "profession": req.profession, "city": req.city,
        "data_subject_email": req.email, "data_subject_phone": req.phone,
        "expertise": req.expertise, "uvp": req.uvp,
        "consent_granted": True,
        "consent_version": req.consent_version if req.consent_version else settings.minimum_consent_version,
        "consent_granted_at": now, "owner_user_id": user.get("id"),
        "retention_until": retention, "created_at": now,
    }
    await db.expert_insert(data)

    await log_consent(
        expert_id=expert_id, consent_type="processing", is_granted=True,
        consent_version=req.consent_version if req.consent_version else settings.minimum_consent_version,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", ""),
    )

    return {"expert_id": expert_id}


@router.patch("/{expert_id}")
async def update_expert(expert_id: str, req: ExpertCardUpdate, user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)
    updates = {}
    for field, value in [("name", req.name), ("nickname", req.nickname), ("age", req.age),
                         ("profession", req.profession), ("city", req.city),
                         ("expertise", req.expertise), ("uvp", req.uvp),
                         ("email", req.email), ("phone", req.phone)]:
        if value is not None:
            updates[field] = value
    if not updates:
        raise HTTPException(400, "Нет данных для обновления")
    await db.expert_update(expert_id, updates)
    return {"status": "updated"}


@router.delete("/{expert_id}")
async def delete_expert(expert_id: str, user: dict = Depends(require_admin)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await db.expert_delete(expert_id)
    return {"deleted": True}
