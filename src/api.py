import logging
import uuid
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .db_client import db
from .db.schemas import (
    ExpertCardCreate, ExpertCardUpdate,
    InterviewStartRequest, InterviewAnswerRequest,
    GenerateContentRequest,
    UserResponse, UserUpdate,
    ConsentRequest, ConsentResponse, ExportRequest, ExportResponse,
    DeletionRequest, DeletionResponse, AuditLogResponse,
)
from .auth import decode_supabase_token
from .interviewer.analyzer import analyze_interview
from .dependencies import get_current_user, require_admin
from .compliance import (
    log_consent, withdraw_consent, request_export, request_deletion,
    audit_log, list_audit_logs, build_export_response, build_deletion_response,
)
from .interviewer.questions import QUESTION_BANK
from .expert_card.card import ExpertCard
from .expert_card.parser import save_card
from .producer_agent.planner import generate_content_plan
from .content_generator.social_post import generate_social_post
from .content_generator.video_script import generate_video_script
from .transcriber.pipeline import transcribe
from .transcriber.youtube import is_youtube_url

# ── Logging ──
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("content-producer")

# ── In-memory interview sessions ──
active_interviews: dict[str, dict] = {}

# ── Rate limiter (naive in-memory dict) ──
_rate_limit_store: dict[str, tuple[int, datetime]] = {}

def rate_limit_check(key: str, max_requests: int = 5, window_seconds: int = 60):
    now = datetime.now(timezone.utc)
    count, first = _rate_limit_store.get(key, (0, now))
    if (now - first).total_seconds() > window_seconds:
        count, first = 0, now
    count += 1
    _rate_limit_store[key] = (count, first)
    if count > max_requests:
        raise HTTPException(status_code=429, detail="Слишком много запросов. Попробуйте позже.")

# ── Lifespan ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Content Producer API started (Supabase mode)")
    yield
    logger.info("Content Producer API shutting down")

# ── App ──
app = FastAPI(
    title="Content Producer API",
    version="0.4.0-supabase",
    description="AI SaaS for expert content creation — RF 152-FZ compliant, Supabase-backed",
    lifespan=lifespan,
)

# ── Middleware ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(",") if settings.cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# Audit log middleware
@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    response = await call_next(request)
    if settings.enable_audit_logging and request.url.path.startswith("/api/"):
        path = request.url.path
        method = request.method
        user_id = None
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent", "")
        if method in ("POST", "PUT", "DELETE", "PATCH"):
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                payload = decode_supabase_token(auth_header.split(" ")[1])
                if payload:
                    user_id = payload.get("sub")
            try:
                await audit_log("api_request", str(uuid.uuid4()), method.lower(),
                               performed_by_user_id=user_id, ip_address=ip, user_agent=ua,
                               details={"path": path})
            except Exception:
                pass
    return response

# ── Helper ──
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


# ═════════════════════════════════════════════════════════
# AUTH (Supabase — no passwords, no register/login)
# ═════════════════════════════════════════════════════════

@app.get("/api/auth/me", response_model=UserResponse)
async def me(user: dict = Depends(get_current_user)):
    return UserResponse(
        id=user.get("id", ""), email=user.get("email", ""), full_name=user.get("full_name", ""), role=user.get("role", "operator"),
        email_verified=user.get("email_verified", False), phone_verified=user.get("phone_verified", False),
        last_login_at=user.get("last_login_at"), created_at=user.get("created_at", datetime.now(timezone.utc).isoformat()),
    )


@app.patch("/api/auth/me")
async def update_me(req: UserUpdate, user: dict = Depends(get_current_user)):
    updates = {}
    if req.full_name is not None:
        updates["full_name"] = req.full_name
    if req.phone is not None:
        updates["phone"] = req.phone
    if updates:
        await db.user_update(user.get("id"), updates)
    return {"status": "updated"}


# ═════════════════════════════════════════════════════════
# EXPERTS (152-FZ: owner_user_id, consent, retention)
# ═════════════════════════════════════════════════════════

@app.get("/api/experts")
async def list_experts(
    skip: int = 0, limit: int = 50,
    user: dict = Depends(get_current_user),
):
    experts = await db.expert_list(skip, limit, owner_user_id=user.get("id"))
    return {"experts": [_to_expert_card_response(e) for e in experts]}


@app.get("/api/experts/{expert_id}")
async def get_expert(expert_id: str, user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    return _to_expert_card_response(e)


@app.post("/api/experts")
async def create_expert(
    req: ExpertCardCreate,
    request: Request,
    user: dict = Depends(get_current_user),
):
    if not req.consent_granted:
        raise HTTPException(status_code=400, detail="Согласие на обработку ПДн обязательно")

    expert_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    retention = (datetime.now(timezone.utc) + timedelta(days=settings.default_retention_days)).isoformat()

    data = {
        "id": expert_id,
        "name": req.name,
        "nickname": req.nickname,
        "age": req.age,
        "profession": req.profession,
        "city": req.city,
        "data_subject_email": req.email,
        "data_subject_phone": req.phone,
        "expertise": req.expertise,
        "uvp": req.uvp,
        "consent_granted": True,
        "consent_version": settings.minimum_consent_version,
        "consent_granted_at": now,
        "owner_user_id": user.get("id"),
        "retention_until": retention,
        "created_at": now,
    }
    await db.expert_insert(data)

    await log_consent(
        expert_id=expert_id,
        consent_type="processing",
        is_granted=True,
        consent_version=settings.minimum_consent_version,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", ""),
    )

    return {"expert_id": expert_id}


@app.patch("/api/experts/{expert_id}")
async def update_expert(
    expert_id: str,
    req: ExpertCardUpdate,
    user: dict = Depends(get_current_user),
):
    updates = {}
    for field, value in [("name", req.name), ("nickname", req.nickname), ("age", req.age),
                         ("profession", req.profession), ("city", req.city), ("expertise", req.expertise),
                         ("uvp", req.uvp), ("email", req.email), ("phone", req.phone)]:
        if value is not None:
            updates[field] = value
    if not updates:
        raise HTTPException(400, "Нет данных для обновления")

    await db.expert_update(expert_id, updates)
    return {"status": "updated"}


@app.delete("/api/experts/{expert_id}")
async def delete_expert(expert_id: str, user: dict = Depends(require_admin)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await db.expert_delete(expert_id)
    return {"deleted": True}


# ═════════════════════════════════════════════════════════
# INTERVIEW
# ═════════════════════════════════════════════════════════

@app.post("/api/interview/start")
async def start_interview(req: InterviewStartRequest, user: dict = Depends(get_current_user)):
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    retention = (datetime.now(timezone.utc) + timedelta(days=settings.interview_retention_days)).isoformat()
    await db.interview_insert({
        "id": session_id,
        "expert_name": req.expert_name,
        "creator_user_id": user.get("id"),
        "retention_until": retention,
        "created_at": now,
        "responses": json.dumps({}),
        "is_complete": False,
    })

    active_interviews[session_id] = {
        "expert_name": req.expert_name,
        "responses": {},
        "asked_questions": [],
        "current_category": "personality",
        "is_complete": False,
    }

    cat = "personality"
    available = [q for q in QUESTION_BANK if q.block == cat]
    q_text = available[0].text if available else None

    return {
        "session_id": session_id,
        "question": q_text,
        "progress": {"answered": 0, "total": len(QUESTION_BANK), "percent": 0},
    }


@app.post("/api/interview/{session_id}/answer")
async def submit_answer(session_id: str, req: InterviewAnswerRequest):
    if session_id not in active_interviews:
        raise HTTPException(404, "Interview session not found")

    data = active_interviews[session_id]
    asked = set(data["asked_questions"])
    available = [q for q in QUESTION_BANK if q.block == data["current_category"] and q.id not in asked]
    if available:
        q = available[0]
        data["responses"][q.id] = req.answer
        data["asked_questions"].append(q.id)

    asked = set(data["asked_questions"])
    available = [q for q in QUESTION_BANK if q.block == data["current_category"] and q.id not in asked]
    if not available:
        cats = ["personality", "expertise", "product"]
        idx = cats.index(data["current_category"])
        if idx < len(cats) - 1:
            data["current_category"] = cats[idx + 1]
            available = [q for q in QUESTION_BANK if q.block == data["current_category"] and q.id not in asked]
        else:
            data["is_complete"] = True

    next_q_text = available[0].text if available else None
    answered = len(data["responses"])
    total = len(QUESTION_BANK)

    return {
        "question": next_q_text,
        "is_complete": data["is_complete"],
        "progress": {"answered": answered, "total": total, "percent": round(answered / total * 100) if total else 0},
    }


@app.post("/api/interview/{session_id}/finalize")
async def finalize_interview(session_id: str, user: dict = Depends(get_current_user)):
    if session_id not in active_interviews:
        raise HTTPException(404, "Interview session not found")

    data = active_interviews[session_id]

    class _Session:
        def __init__(self, d):
            self.expert_name = d["expert_name"]
            self.responses = d["responses"]
            self.asked_questions = list(d["responses"].keys())
            self.is_complete = True

    session = _Session(data)
    card = await analyze_interview(session, settings.openai_api_key)

    expert_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    retention = (datetime.now(timezone.utc) + timedelta(days=settings.default_retention_days)).isoformat()
    await db.expert_insert({
        "id": expert_id,
        "name": card.name or data["expert_name"],
        "nickname": card.nickname,
        "profession": card.profession,
        "expertise": card.expertise if isinstance(card.expertise, list) else card.expertise,
        "uvp": card.uvp,
        "tone_style": card.tone.style if card.tone else "",
        "tone_format_pref": card.tone.format_pref if card.tone else "",
        "tone_emoji_style": card.tone.emoji_style if card.tone else "",
        "stories": json.dumps(card.stories) if isinstance(card.stories, list) else card.stories,
        "achievements": json.dumps(card.achievements) if isinstance(card.achievements, list) else card.achievements,
        "consent_granted": True,
        "consent_granted_at": now,
        "consent_version": settings.minimum_consent_version,
        "owner_user_id": user.get("id"),
        "retention_until": retention,
        "created_at": now,
    })

    # Save local .md (optional, for export)
    experts_dir = Path("experts")
    experts_dir.mkdir(exist_ok=True)
    safe_name = (card.name or data["expert_name"]).lower().replace(" ", "_").replace("/", "_")
    save_path = experts_dir / f"{safe_name}.md"
    save_card(card, save_path)

    del active_interviews[session_id]
    return {"expert_id": expert_id, "card": card.model_dump(), "saved_to": str(save_path)}


# ═════════════════════════════════════════════════════════
# TRANSCRIPTION
# ═════════════════════════════════════════════════════════

@app.post("/api/transcribe/youtube")
async def transcribe_youtube(
    expert_name: str,
    youtube_url: str,
    language: str = "ru",
    expert_id: str | None = None,
    user: dict = Depends(get_current_user),
):
    if not settings.openai_api_key:
        raise HTTPException(500, "OPENAI_API_KEY not configured")
    if not is_youtube_url(youtube_url):
        raise HTTPException(400, "Not a valid YouTube URL")

    text = await transcribe(youtube_url, "youtube", settings.openai_api_key, language)
    tid = str(uuid.uuid4())
    await db.transcription_insert({
        "id": tid,
        "expert_id": expert_id,
        "source_url": youtube_url,
        "source_type": "youtube",
        "text": text,
        "language": language,
        "creator_user_id": user.get("id"),
        "retention_until": (datetime.now(timezone.utc) + timedelta(days=settings.transcription_retention_days)).isoformat(),
    })
    return {"transcription_id": tid, "expert_name": expert_name, "text_length": len(text), "preview": text[:300]}


@app.post("/api/transcribe/upload")
async def transcribe_upload(
    expert_name: str = Form(...),
    file: UploadFile = File(...),
    language: str = Form("ru"),
    expert_id: str | None = Form(None),
    user: dict = Depends(get_current_user),
):
    if not settings.openai_api_key:
        raise HTTPException(500, "OPENAI_API_KEY not configured")
    import tempfile
    suffix = Path(file.filename).suffix if file.filename else ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        text = await transcribe(tmp_path, "file", settings.openai_api_key, language)
    except Exception as e:
        logger.exception("Upload transcription failed")
        raise HTTPException(500, str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    tid = str(uuid.uuid4())
    await db.transcription_insert({
        "id": tid, "expert_id": expert_id, "source_url": file.filename or "upload",
        "source_type": "file", "text": text, "language": language,
        "creator_user_id": user.get("id"),
        "retention_until": (datetime.now(timezone.utc) + timedelta(days=settings.transcription_retention_days)).isoformat(),
    })
    return {"transcription_id": tid, "expert_name": expert_name, "text_length": len(text), "preview": text[:300]}


@app.get("/api/transcribe/{transcription_id}")
async def get_transcription(transcription_id: str, user: dict = Depends(get_current_user)):
    # In-memory fallback: just search all transcriptions
    trans = await db.transcription_list(None)  # None returns all
    t = next((x for x in trans if x.get("id") == transcription_id), None)
    if not t:
        raise HTTPException(404, "Transcription not found")
    return {"id": t.get("id"), "expert_id": t.get("expert_id"), "source_url": t.get("source_url"), "text": t.get("text"), "language": t.get("language"), "created_at": t.get("created_at")}


# ═════════════════════════════════════════════════════════
# CONTENT
# ═════════════════════════════════════════════════════════

@app.post("/api/experts/{expert_id}/content")
async def generate_content(expert_id: str, req: GenerateContentRequest, user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    card = ExpertCard(
        name=e.get("name"), profession=e.get("profession"),
        expertise=json.loads(e.get("expertise", "[]") or "[]"),
    )
    if req.content_type == "post":
        content = await generate_social_post(card, req.topic, req.platform, settings.openai_api_key)
    elif req.content_type == "video":
        content = await generate_video_script(card, req.topic, api_key=settings.openai_api_key)
    else:
        raise HTTPException(400, "Unsupported content type")

    content_id = str(uuid.uuid4())
    body_text = content if isinstance(content, str) else json.dumps(content)
    await db.content_insert({
        "id": content_id, "expert_id": expert_id, "content_type": req.content_type,
        "topic": req.topic, "platform": req.platform, "content": body_text,
        "creator_user_id": user.get("id"),
    })
    return {"content_id": content_id, "content": content}


@app.get("/api/experts/{expert_id}/content")
async def get_expert_content(expert_id: str, skip: int = 0, limit: int = 20, user: dict = Depends(get_current_user)):
    items = await db.content_list(expert_id, skip, limit)
    return {"items": [
        {"id": i.get("id"), "type": i.get("content_type"), "topic": i.get("topic"),
         "platform": i.get("platform"), "status": i.get("status"), "created_at": i.get("created_at")}
        for i in items
    ]}


@app.post("/api/experts/{expert_id}/plan")
async def get_content_plan(expert_id: str, days: int = 7, user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    card = ExpertCard(name=e.get("name"), profession=e.get("profession"),
                      expertise=json.loads(e.get("expertise", "[]") or "[]"))
    plan = generate_content_plan(card, days)
    return {"plan": plan}


# ═════════════════════════════════════════════════════════
# 152-FZ COMPLIANCE
# ═════════════════════════════════════════════════════════

@app.post("/api/experts/{expert_id}/consent", response_model=ConsentResponse)
async def grant_consent(
    expert_id: str,
    req: ConsentRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")

    log = await log_consent(
        expert_id=expert_id,
        consent_type=req.consent_type,
        is_granted=req.is_granted,
        consent_version=req.consent_version or settings.minimum_consent_version,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", ""),
    )
    return ConsentResponse(
        id=log.get("id"),
        consent_type=log.get("consent_type"),
        consent_version=log.get("consent_version"),
        is_granted=log.get("is_granted"),
        granted_at=log.get("granted_at"),
    )


@app.delete("/api/experts/{expert_id}/consent/{consent_type}")
async def delete_consent(
    expert_id: str,
    consent_type: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await withdraw_consent(expert_id, consent_type)
    return {"status": "consent_withdrawn", "expert_id": expert_id}


@app.post("/api/experts/{expert_id}/export", response_model=ExportResponse)
async def request_data_export(
    expert_id: str,
    req: ExportRequest,
    user: dict = Depends(get_current_user),
):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    if not e.get("consent_granted"):
        raise HTTPException(403, "Согласие на обработку не предоставлено")

    request_id = await request_export(expert_id, req.export_format, req.include_transcriptions)
    await audit_log("data_export_log", request_id, "create",
                   performed_by_user_id=user.get("id"),
                   details={"format": req.export_format, "expert_id": expert_id})
    return ExportResponse(request_id=request_id, status="processing")


@app.get("/api/export/{request_id}")
async def get_export_status(request_id: str, user: dict = Depends(get_current_user)):
    row = await db.export_get(request_id)
    if not row:
        raise HTTPException(404, "Export request not found")
    return build_export_response(row)


@app.post("/api/experts/{expert_id}/delete", response_model=DeletionResponse)
async def request_data_deletion(
    expert_id: str,
    req: DeletionRequest,
    user: dict = Depends(get_current_user),
):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")

    request_id = await request_deletion(expert_id, req.reason, req.deletion_scope)
    expected = datetime.now(timezone.utc) + timedelta(hours=settings.deletion_grace_hours)
    await audit_log("data_deletion_log", expert_id, "delete_request",
                   performed_by_user_id=user.get("id"),
                   details={"scope": req.deletion_scope, "request_id": request_id})
    return DeletionResponse(request_id=request_id, status="pending", expected_completion=expected)


@app.get("/api/deletion/{request_id}")
async def get_deletion_status(request_id: str, user: dict = Depends(get_current_user)):
    row = await db.deletion_get(request_id)
    if not row:
        raise HTTPException(404, "Deletion request not found")
    return build_deletion_response(row)


@app.get("/api/audit")
async def list_audit(
    table_name: str | None = None,
    action: str | None = None,
    skip: int = 0,
    limit: int = 100,
    user: dict = Depends(require_admin),
):
    total, logs = await list_audit_logs(limit, skip, table_name=table_name, action=action)
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "logs": [
            {"id": l.get("id"), "action": l.get("action"), "table_name": l.get("table_name"),
             "record_id": l.get("record_id"), "details": json.loads(l.get("details", "{}")), "ip_address": l.get("ip_address"),
             "created_at": l.get("created_at")}
            for l in logs
        ],
    }


@app.get("/api/info/operator")
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


# ═════════════════════════════════════════════════════════
# HEALTH
# ═════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.4.0-supabase", "compliance": "152-FZ"}


@app.get("/")
async def root():
    return {"name": "Content Producer API", "version": "0.4.0", "docs": "/docs", "compliance": "152-FZ"}
