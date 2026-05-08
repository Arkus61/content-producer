"""Compliance endpoints — 152-FZ."""
import json
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request
from ..config import settings
from ..db_client import db
from ..db.schemas import ConsentRequest, ConsentResponse, ExportRequest, ExportResponse, DeletionRequest, DeletionResponse
from ..dependencies import get_current_user, require_admin, require_expert_owner
from ..compliance import (
    log_consent, withdraw_consent, request_export, request_deletion,
    audit_log, list_audit_logs, build_export_response, build_deletion_response,
)

router = APIRouter(tags=["compliance"])


@router.post("/api/experts/{expert_id}/consent", response_model=ConsentResponse)
async def grant_consent(expert_id: str, req: ConsentRequest, request: Request,
                        user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)

    log = await log_consent(
        expert_id=expert_id, consent_type=req.consent_type, is_granted=req.is_granted,
        consent_version=req.consent_version or settings.minimum_consent_version,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", ""),
    )
    return ConsentResponse(
        id=log.get("id"), consent_type=log.get("consent_type"),
        consent_version=log.get("consent_version"),
        is_granted=log.get("is_granted"), granted_at=log.get("granted_at"),
    )


@router.delete("/api/experts/{expert_id}/consent/{consent_type}")
async def delete_consent(expert_id: str, consent_type: str, request: Request,
                         user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)
    await withdraw_consent(expert_id, consent_type)
    return {"status": "consent_withdrawn", "expert_id": expert_id}


@router.post("/api/experts/{expert_id}/export", response_model=ExportResponse)
async def request_data_export(expert_id: str, req: ExportRequest,
                              user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)
    if not e.get("consent_granted"):
        raise HTTPException(403, "Согласие на обработку не предоставлено")
    request_id = await request_export(expert_id, req.export_format, req.include_transcriptions)
    await audit_log("data_export_log", request_id, "create",
                    performed_by_user_id=user.get("id"),
                    details={"format": req.export_format, "expert_id": expert_id})
    return ExportResponse(request_id=request_id, status="processing")


@router.get("/api/export/{request_id}")
async def get_export_status(request_id: str, user: dict = Depends(get_current_user)):
    row = await db.export_get(request_id)
    if not row:
        raise HTTPException(404, "Export request not found")
    expert = await db.expert_get(row.get("expert_id"))
    if not expert:
        raise HTTPException(404, "Export request not found")
    if user.get("role") != "admin" and expert.get("owner_user_id") != user.get("id"):
        raise HTTPException(403, "Нет доступа")
    return build_export_response(row)


@router.post("/api/experts/{expert_id}/delete", response_model=DeletionResponse)
async def request_data_deletion(expert_id: str, req: DeletionRequest,
                                user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)
    request_id = await request_deletion(expert_id, req.reason, req.deletion_scope)
    expected = datetime.now(timezone.utc) + timedelta(hours=settings.deletion_grace_hours)
    await audit_log("data_deletion_log", expert_id, "delete_request",
                    performed_by_user_id=user.get("id"),
                    details={"scope": req.deletion_scope, "request_id": request_id})
    return DeletionResponse(request_id=request_id, status="pending", expected_completion=expected)


@router.get("/api/deletion/{request_id}")
async def get_deletion_status(request_id: str, user: dict = Depends(get_current_user)):
    row = await db.deletion_get(request_id)
    if not row:
        raise HTTPException(404, "Deletion request not found")
    expert = await db.expert_get(row.get("expert_id"))
    if not expert:
        raise HTTPException(404, "Deletion request not found")
    if user.get("role") != "admin" and expert.get("owner_user_id") != user.get("id"):
        raise HTTPException(403, "Нет доступа")
    return build_deletion_response(row)


@router.get("/api/audit")
async def list_audit(table_name: str | None = None, action: str | None = None,
                     skip: int = 0, limit: int = 100,
                     user: dict = Depends(require_admin)):
    total, logs = await list_audit_logs(limit, skip, table_name=table_name, action=action)
    return {
        "total": total, "skip": skip, "limit": limit,
        "logs": [{"id": l.get("id"), "action": l.get("action"),
                  "table_name": l.get("table_name"), "record_id": l.get("record_id"),
                  "details": json.loads(l.get("details", "{}")),
                  "ip_address": l.get("ip_address"), "created_at": l.get("created_at")}
                 for l in logs],
    }


@router.get("/api/info/operator")
async def operator_info():
    return {
        "operator_name": settings.operator_name,
        "operator_address": settings.operator_address,
        "operator_inn": settings.operator_inn,
        "operator_email": settings.operator_email,
        "operator_phone": settings.operator_phone,
        "dpo_email": settings.operator_dpo_email,
        "dpo_phone": settings.operator_dpo_phone,
        "privacy_policy_url": settings.privacy_policy_url,
        "consent_document_url": settings.consent_document_url,
        "retention_days": settings.default_retention_days,
    }
