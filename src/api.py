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
from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db.engine import async_engine as engine, async_session_factory as async_session
from .db.models import Base, ExpertCardModel, InterviewSessionModel, TranscriptionModel, ContentItemModel, User
from .db.schemas import (
    ExpertCardCreate, ExpertCardResponse, ExpertCardUpdate,
    InterviewStartRequest, InterviewAnswerRequest,
    GenerateContentRequest, TranscriptionResponse, ContentPlanResponse,
    PaginationParams, PaginatedResponse,
    UserResponse, UserUpdate,
    ConsentRequest, ConsentResponse, ExportRequest, ExportResponse,
    DeletionRequest, DeletionResponse, AuditLogResponse,
)
from .auth import decode_supabase_token, get_user_by_id
from .dependencies import get_current_user, require_admin
from .compliance import (
    consent_service, data_export_service, data_deletion_service,
    audit_service, retention_service, encryption_service,
)
from .interviewer.session import InterviewSession
from .interviewer.analyzer import analyze_interview
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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")
    yield
    await engine.dispose()
    logger.info("Database engine disposed")

# ── App ──
app = FastAPI(
    title="Content Producer API",
    version="0.3.0-152fz",
    description="AI SaaS for expert content creation — RF 152-FZ compliant",
    lifespan=lifespan,
)

# ── Middleware ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(",") if settings.cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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
        # simple audit for state-changing operations
        if method in ("POST", "PUT", "DELETE", "PATCH") and "login" not in path and "register" not in path:
            try:
                async with async_session() as session:
                    auth_header = request.headers.get("authorization", "")
                    if auth_header.startswith("Bearer "):
                        payload = decode_token(auth_header.split(" ")[1])
                        if payload:
                            user_id = payload.get("sub")
                    await audit_service.log(
                        session=session,
                        table_name="api_request",
                        record_id=str(uuid.uuid4()),
                        action=method.lower(),
                        performed_by_user_id=user_id,
                        ip_address=ip,
                        user_agent=ua,
                        details={"path": path},
                    )
            except Exception:
                pass
    return response

# ── Helper ──
def _to_expert_card_response(model: ExpertCardModel) -> dict:
    return {
        "id": model.id,
        "name": model.name,
        "nickname": model.nickname,
        "age": model.age,
        "profession": model.profession,
        "city": model.city,
        "email": model.data_subject_email,
        "phone": model.data_subject_phone,
        "expertise": json.loads(model.expertise) if model.expertise else [],
        "uvp": model.uvp,
        "consent_granted": model.consent_granted,
        "consent_granted_at": model.consent_granted_at,
        "is_anonymized": model.is_anonymized,
        "retention_until": model.retention_until,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }

# ═════════════════════════════════════════════════════════
# AUTH (Supabase — no passwords, no register/login)
# ═════════════════════════════════════════════════════════

@app.get("/api/auth/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=user.id, email=user.email, full_name=user.full_name, role=user.role,
        email_verified=user.email_verified, phone_verified=user.phone_verified,
        last_login_at=user.last_login_at, created_at=user.created_at,
    )


@app.patch("/api/auth/me")
async def update_me(req: UserUpdate, user: User = Depends(get_current_user)):
    async with async_session() as session:
        if req.full_name is not None:
            user.full_name = req.full_name
        if req.phone is not None:
            user.phone = req.phone
        await session.commit()
    return {"status": "updated"}


# ═════════════════════════════════════════════════════════
# EXPERTS (152-FZ: owner_user_id, consent, retention)
# ═════════════════════════════════════════════════════════

@app.get("/api/experts")
async def list_experts(
    skip: int = 0, limit: int = 50,
    user: User = Depends(get_current_user),
):
    async with async_session() as session:
        result = await session.execute(
            select(ExpertCardModel)
            .order_by(ExpertCardModel.created_at.desc())
            .offset(skip).limit(limit)
        )
        experts = result.scalars().all()
    return {"experts": [_to_expert_card_response(e) for e in experts]}


@app.get("/api/experts/{expert_id}")
async def get_expert(expert_id: str, user: User = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(select(ExpertCardModel).where(ExpertCardModel.id == expert_id))
        e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(404, "Expert not found")
    return _to_expert_card_response(e)


@app.post("/api/experts")
async def create_expert(
    req: ExpertCardCreate,
    request: Request,
    user: User = Depends(get_current_user),
):
    # 152-FZ: require consent for new expert
    if not req.consent_granted:
        raise HTTPException(status_code=400, detail="Согласие на обработку ПДн обязательно")

    expert_id = str(uuid.uuid4())
    async with async_session() as session:
        db_card = ExpertCardModel(
            id=expert_id,
            name=req.name,
            nickname=req.nickname,
            age=req.age,
            profession=req.profession,
            city=req.city,
            data_subject_email=req.email,
            data_subject_phone=req.phone,
            expertise=json.dumps(req.expertise),
            uvp=req.uvp,
            consent_granted=True,
            consent_version=settings.minimum_consent_version,
            consent_granted_at=datetime.now(timezone.utc),
            owner_user_id=user.id,
            retention_until=datetime.now(timezone.utc) + timedelta(days=settings.default_retention_days),
        )
        session.add(db_card)
        # Log consent
        await consent_service.log_consent(
            session=session,
            expert_id=expert_id,
            consent_type="processing",
            is_granted=True,
            consent_version=settings.minimum_consent_version,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", ""),
        )
        await session.commit()

    return {"expert_id": expert_id}


@app.patch("/api/experts/{expert_id}")
async def update_expert(
    expert_id: str,
    req: ExpertCardUpdate,
    user: User = Depends(get_current_user),
):
    async with async_session() as session:
        result = await session.execute(select(ExpertCardModel).where(ExpertCardModel.id == expert_id))
        e = result.scalar_one_or_none()
        if not e:
            raise HTTPException(404, "Expert not found")

        if req.name is not None:
            e.name = req.name
        if req.nickname is not None:
            e.nickname = req.nickname
        if req.age is not None:
            e.age = req.age
        if req.profession is not None:
            e.profession = req.profession
        if req.city is not None:
            e.city = req.city
        if req.expertise is not None:
            e.expertise = json.dumps(req.expertise)
        if req.uvp is not None:
            e.uvp = req.uvp
        if req.email is not None:
            e.data_subject_email = req.email
        if req.phone is not None:
            e.data_subject_phone = req.phone

        e.updated_at = datetime.now(timezone.utc)
        await session.commit()

    return {"status": "updated"}


@app.delete("/api/experts/{expert_id}")
async def delete_expert(expert_id: str, user: User = Depends(require_admin)):
    async with async_session() as session:
        result = await session.execute(select(ExpertCardModel).where(ExpertCardModel.id == expert_id))
        e = result.scalar_one_or_none()
        if not e:
            raise HTTPException(404, "Expert not found")
        await session.delete(e)
        await session.commit()
    return {"deleted": True}


# ═════════════════════════════════════════════════════════
# INTERVIEW
# ═════════════════════════════════════════════════════════

@app.post("/api/interview/start")
async def start_interview(req: InterviewStartRequest, user: User = Depends(get_current_user)):
    session_id = str(uuid.uuid4())
    db_session = InterviewSessionModel(
        id=session_id,
        expert_name=req.expert_name,
        creator_user_id=user.id,
        retention_until=datetime.now(timezone.utc) + timedelta(days=settings.interview_retention_days),
    )
    async with async_session() as session:
        session.add(db_session)
        await session.commit()

    active_interviews[session_id] = {
        "expert_name": req.expert_name,
        "responses": {},
        "asked_questions": [],
        "current_category": "personality",
        "is_complete": False,
    }

    cat = "personality"
    asked = set()
    available = [q for q in QUESTION_BANK if q.block == cat and q.id not in asked]
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

    # next question
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
        "progress": {"answered": answered, "total": total, "percent": round(answered / total * 100)},
    }


@app.post("/api/interview/{session_id}/finalize")
async def finalize_interview(session_id: str, user: User = Depends(get_current_user)):
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
    async with async_session() as db:
        db_card = ExpertCardModel(
            id=expert_id,
            name=card.name or data["expert_name"],
            nickname=card.nickname,
            profession=card.profession,
            expertise=card.expertise,
            uvp=card.uvp,
            tone_style=card.tone.style,
            tone_format_pref=card.tone.format_pref,
            tone_emoji_style=card.tone.emoji_style,
            stories=json.dumps(card.stories),
            achievements=json.dumps(card.achievements),
            consent_granted=True,
            consent_granted_at=datetime.now(timezone.utc),
            consent_version=settings.minimum_consent_version,
            owner_user_id=user.id,
            retention_until=datetime.now(timezone.utc) + timedelta(days=settings.default_retention_days),
        )
        db.add(db_card)
        await db.commit()

    # Save local .md
    experts_dir = Path("experts")
    experts_dir.mkdir(exist_ok=True)
    save_path = experts_dir / f"{card.name.lower().replace(' ', '_')}.md"
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
    user: User = Depends(get_current_user),
):
    if not settings.openai_api_key:
        raise HTTPException(500, "OPENAI_API_KEY not configured")
    if not is_youtube_url(youtube_url):
        raise HTTPException(400, "Not a valid YouTube URL")

    text = await transcribe(youtube_url, "youtube", settings.openai_api_key, language)
    tid = str(uuid.uuid4())
    async with async_session() as session:
        db_trans = TranscriptionModel(
            id=tid,
            expert_id=expert_id,
            source_url=youtube_url,
            source_type="youtube",
            text=text,
            language=language,
            creator_user_id=user.id,
            retention_until=datetime.now(timezone.utc) + timedelta(days=settings.transcription_retention_days),
        )
        session.add(db_trans)
        await session.commit()
    return {"transcription_id": tid, "expert_name": expert_name, "text_length": len(text), "preview": text[:300]}


@app.post("/api/transcribe/upload")
async def transcribe_upload(
    expert_name: str = Form(...),
    file: UploadFile = File(...),
    language: str = Form("ru"),
    expert_id: str | None = Form(None),
    user: User = Depends(get_current_user),
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
    async with async_session() as session:
        db_trans = TranscriptionModel(
            id=tid, expert_id=expert_id, source_url=file.filename or "upload",
            source_type="file", text=text, language=language,
            creator_user_id=user.id,
            retention_until=datetime.now(timezone.utc) + timedelta(days=settings.transcription_retention_days),
        )
        session.add(db_trans)
        await session.commit()
    return {"transcription_id": tid, "expert_name": expert_name, "text_length": len(text), "preview": text[:300]}


@app.get("/api/transcribe/{transcription_id}")
async def get_transcription(transcription_id: str, user: User = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(select(TranscriptionModel).where(TranscriptionModel.id == transcription_id))
        t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Transcription not found")
    return {"id": t.id, "expert_id": t.expert_id, "source_url": t.source_url, "text": t.text, "language": t.language, "created_at": t.created_at}


# ═════════════════════════════════════════════════════════
# CONTENT
# ═════════════════════════════════════════════════════════

@app.post("/api/experts/{expert_id}/content")
async def generate_content(expert_id: str, req: GenerateContentRequest, user: User = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(select(ExpertCardModel).where(ExpertCardModel.id == expert_id))
        e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(404, "Expert not found")
    card = ExpertCard(
        name=e.name, profession=e.profession, expertise=json.loads(e.expertise) if e.expertise else [],
    )
    if req.content_type == "post":
        content = await generate_social_post(card, req.topic, req.platform, settings.openai_api_key)
    elif req.content_type == "video":
        content = await generate_video_script(card, req.topic, api_key=settings.openai_api_key)
    else:
        raise HTTPException(400, "Unsupported content type")

    content_id = str(uuid.uuid4())
    body_text = content if isinstance(content, str) else json.dumps(content)
    async with async_session() as session:
        db = ContentItemModel(
            id=content_id, expert_id=expert_id, content_type=req.content_type,
            topic=req.topic, platform=req.platform, content=body_text,
            creator_user_id=user.id,
        )
        session.add(db)
        await session.commit()
    return {"content_id": content_id, "content": content}


@app.get("/api/experts/{expert_id}/content")
async def get_expert_content(expert_id: str, skip: int = 0, limit: int = 20, user: User = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(ContentItemModel)
            .where(ContentItemModel.expert_id == expert_id)
            .order_by(ContentItemModel.created_at.desc())
            .offset(skip).limit(limit)
        )
        items = result.scalars().all()
    return {"items": [{"id": i.id, "type": i.content_type, "topic": i.topic, "platform": i.platform, "status": i.status, "created_at": i.created_at} for i in items]}


@app.post("/api/experts/{expert_id}/plan")
async def get_content_plan(expert_id: str, days: int = 7, user: User = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(select(ExpertCardModel).where(ExpertCardModel.id == expert_id))
        e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(404, "Expert not found")
    card = ExpertCard(name=e.name, profession=e.profession, expertise=json.loads(e.expertise))
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
    user: User = Depends(get_current_user),
):
    """Log data-subject consent (Art. 9 152-FZ)."""
    async with async_session() as session:
        result = await session.execute(select(ExpertCardModel).where(ExpertCardModel.id == expert_id))
        expert = result.scalar_one_or_none()
        if not expert:
            raise HTTPException(404, "Expert not found")

        log = await consent_service.log_consent(
            session=session,
            expert_id=expert_id,
            consent_type=req.consent_type,
            is_granted=req.is_granted,
            consent_version=req.consent_version or settings.minimum_consent_version,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", ""),
        )
        return ConsentResponse(
            id=log.id,
            consent_type=log.consent_type,
            consent_version=log.consent_version,
            is_granted=log.is_granted,
            granted_at=log.granted_at,
        )


@app.delete("/api/experts/{expert_id}/consent/{consent_type}")
async def withdraw_consent(
    expert_id: str,
    consent_type: str,
    request: Request,
    user: User = Depends(get_current_user),
):
    """Withdraw consent (Art. 9 para 4 152-FZ)."""
    async with async_session() as session:
        result = await session.execute(select(ExpertCardModel).where(ExpertCardModel.id == expert_id))
        expert = result.scalar_one_or_none()
        if not expert:
            raise HTTPException(404, "Expert not found")

        await consent_service.withdraw_consent(
            session=session,
            expert_id=expert_id,
            consent_type=consent_type,
            ip_address=request.client.host if request.client else None,
        )
        await audit_service.log(
            session=session,
            table_name="consent_log",
            record_id=expert_id,
            action="withdraw",
            performed_by_user_id=user.id,
            ip_address=request.client.host if request.client else None,
            details={"consent_type": consent_type},
        )
    return {"status": "consent_withdrawn", "expert_id": expert_id}


@app.post("/api/experts/{expert_id}/export", response_model=ExportResponse)
async def request_data_export(
    expert_id: str,
    req: ExportRequest,
    user: User = Depends(get_current_user),
):
    """Request copy of PDn (Art. 14.1 152-FZ)."""
    async with async_session() as session:
        result = await session.execute(select(ExpertCardModel).where(ExpertCardModel.id == expert_id))
        expert = result.scalar_one_or_none()
        if not expert:
            raise HTTPException(404, "Expert not found")
        if not expert.consent_granted:
            raise HTTPException(403, "Согласие на обработку не предоставлено")

        request_id = await data_export_service.request_export(
            session=session,
            expert_id=expert_id,
            export_format=req.export_format,
            include_transcriptions=req.include_transcriptions,
        )
        await audit_service.log(
            session=session,
            table_name="data_export_log",
            record_id=request_id,
            action="create",
            performed_by_user_id=user.id,
            details={"format": req.export_format, "expert_id": expert_id},
        )
    return ExportResponse(request_id=request_id, status="processing")


@app.get("/api/export/{request_id}")
async def get_export_status(request_id: str, user: User = Depends(get_current_user)):
    async with async_session() as session:
        status = await data_export_service.get_export_status(session, request_id)
    if not status:
        raise HTTPException(404, "Export request not found")
    return status


@app.post("/api/experts/{expert_id}/delete", response_model=DeletionResponse)
async def request_data_deletion(
    expert_id: str,
    req: DeletionRequest,
    user: User = Depends(get_current_user),
):
    """Request deletion of PDn (Art. 14 152-FZ)."""
    async with async_session() as session:
        result = await session.execute(select(ExpertCardModel).where(ExpertCardModel.id == expert_id))
        expert = result.scalar_one_or_none()
        if not expert:
            raise HTTPException(404, "Expert not found")

        request_id = await data_deletion_service.request_deletion(
            session=session,
            expert_id=expert_id,
            reason=req.reason,
            deletion_scope=req.deletion_scope,
            requested_by_user_id=user.id,
        )
        expected = datetime.now(timezone.utc) + timedelta(hours=settings.deletion_grace_hours)
        await audit_service.log(
            session=session,
            table_name="data_deletion_log",
            record_id=expert_id,
            action="delete_request",
            performed_by_user_id=user.id,
            details={"scope": req.deletion_scope, "request_id": request_id},
        )
    return DeletionResponse(request_id=request_id, status="pending", expected_completion=expected)


@app.get("/api/deletion/{request_id}")
async def get_deletion_status(request_id: str, user: User = Depends(get_current_user)):
    async with async_session() as session:
        status = await data_deletion_service.get_deletion_status(session, request_id)
    if not status:
        raise HTTPException(404, "Deletion request not found")
    return status


@app.get("/api/audit")
async def list_audit_logs(
    table_name: str | None = None,
    action: str | None = None,
    skip: int = 0,
    limit: int = 100,
    user: User = Depends(require_admin),
):
    """View audit trail (Art. 18.1 152-FZ) — admin only."""
    async with async_session() as session:
        logs = await audit_service.list_logs(session, table_name=table_name, action=action, skip=skip, limit=limit)
    return {
        "total": len(logs),
        "skip": skip,
        "limit": limit,
        "logs": [
            AuditLogResponse(
                id=l.id, action=l.action, table_name=l.table_name,
                record_id=l.record_id, details=l.details, ip_address=l.ip_address,
                created_at=l.created_at,
            ).model_dump()
            for l in logs
        ],
    }


@app.post("/api/admin/retention/cleanup")
async def enforce_retention(user: User = Depends(require_admin)):
    """Manually trigger retention cleanup (admin only)."""
    async with async_session() as session:
        deleted = await retention_service.enforce_retention(session)
        await audit_service.log(
            session=session,
            table_name="system",
            record_id="retention_cleanup",
            action="cleanup",
            performed_by_user_id=user.id,
            details=deleted,
        )
    return {"deleted": deleted}


@app.get("/api/info/operator")
async def operator_info():
    """Public: operator info per Art. 18.1 152-FZ."""
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
    return {"status": "ok", "version": "0.3.0-152fz", "compliance": "152-FZ"}


@app.get("/")
async def root():
    return {"name": "Content Producer API", "version": "0.3.0", "docs": "/docs", "compliance": "152-FZ"}
