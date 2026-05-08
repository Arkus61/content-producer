import logging
import uuid
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
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
from .dependencies import get_current_user, require_admin, require_expert_owner
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
from .content_pipeline.dispatcher import PipelineDispatcher
from .content_pipeline.style_adapter import StyleAdapter
from .content_pipeline.skill_loader import SkillRegistry
from .content_pipeline.memory_agent import MemoryAgent
from .social_integrations import (
    PublishRequest, PublishResponse, SocialPublisher,
    TelegramPoster, InstagramPoster,
    PreviewRequest, PreviewResponse,
)
from .payment import (
    SubscriptionService, CreateSubscriptionRequest, SubscriptionResponse,
    ProdamusWebhookHandler, ProdamusClient,
)

# ── Logging ──
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("content-producer")

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
                logger.warning("Audit logging failed for %s %s", method, path, exc_info=True)
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


def _filter_fields_for_user(row: dict, user: dict) -> dict:
    """Strip sensitive PDn fields from expert row unless user is owner or admin."""
    resp = dict(row)
    is_owner = (resp.get("owner_user_id") == user.get("id"))
    is_admin = (user.get("role") == "admin")
    if not (is_owner or is_admin):
        resp.pop("data_subject_email", None)
        resp.pop("data_subject_phone", None)
    return resp

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
    if user.get("role") == "admin":
        experts = await db.expert_list(skip, limit)
    else:
        experts = await db.expert_list(skip, limit, owner_user_id=user.get("id"))
    return {"experts": [_to_expert_card_response(_filter_fields_for_user(e, user)) for e in experts]}


@app.get("/api/experts/{expert_id}")
async def get_expert(expert_id: str, user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)
    return _to_expert_card_response(_filter_fields_for_user(e, user))


@app.post("/api/experts")
async def create_expert(
    req: ExpertCardCreate,
    request: Request,
    user: dict = Depends(get_current_user),
):
    if not req.consent_granted:
        raise HTTPException(status_code=400, detail="Согласие на обработку ПДн обязательно")

    if getattr(req, "consent_version", "") and req.consent_version < settings.minimum_consent_version:
        raise HTTPException(status_code=400, detail=f"Consent version must be >= {settings.minimum_consent_version}")

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
        "consent_version": req.consent_version if req.consent_version else settings.minimum_consent_version,
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
        consent_version=req.consent_version if req.consent_version else settings.minimum_consent_version,
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
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)
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
async def submit_answer(session_id: str, req: InterviewAnswerRequest, user: dict = Depends(get_current_user)):
    sess = await db.interview_get(session_id)
    if not sess or sess.get("creator_user_id") != user.get("id"):
        raise HTTPException(403, "Нет доступа к сессии интервью")
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
    if user.get("role") == "admin":
        t = await db.transcription_get(transcription_id)
    else:
        trans = await db.transcription_list(expert_id=None, creator_user_id=user.get("id"))
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
    await require_expert_owner(expert_id, user)
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
        "retention_until": (datetime.now(timezone.utc) + timedelta(days=settings.default_retention_days)).isoformat(),
    })
    return {"content_id": content_id, "content": content}


@app.post("/api/experts/{expert_id}/content/v2")
async def generate_content_v2(expert_id: str, req: GenerateContentRequest, user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)
    # Build card with expert_id embedded
    card = ExpertCard(
        name=e.get("name"), profession=e.get("profession"),
        expertise=json.loads(e.get("expertise", "[]") or "[]"),
    )
    # Inject expert_id as extra attribute for style adapter
    card.id = expert_id

    # Load existing style profile from DB if present
    style_data = {
        "vocabulary": json.loads(e.get("style_vocabulary", "[]") or "[]"),
        "sentence_length": e.get("style_sentence_length", "mixed"),
        "humor_level": e.get("style_humor_level", 5),
        "emoji_usage": e.get("style_emoji_usage", "moderate"),
        "story_structure": e.get("style_story_structure", "hook-story-lesson"),
        "call_to_action_style": e.get("style_call_to_action_style", "soft"),
        "update_count": e.get("style_update_count", 0),
    }
    for key, val in style_data.items():
        setattr(card.style, key, val)

    pipeline = PipelineDispatcher(api_key=settings.openai_api_key)
    result = await pipeline.run(card, req.topic, req.platform)

    # Persist updated style profile to DB
    adapter = StyleAdapter()
    await adapter.write_to_db(card, db)

    content_id = str(uuid.uuid4())
    await db.content_insert({
        "id": content_id, "expert_id": expert_id, "content_type": req.content_type,
        "topic": req.topic, "platform": req.platform,
        "content": json.dumps({
            "content": result.get("content"),
            "visual_brief": result.get("visual_brief"),
            "score": result.get("score"),
            "iterations": result.get("iterations"),
            "task_id": result.get("task_id"),
            "logs": result.get("logs"),
        }, ensure_ascii=False),
        "creator_user_id": user.get("id"),
        "retention_until": (datetime.now(timezone.utc) + timedelta(days=settings.default_retention_days)).isoformat(),
    })

    return {
        "content_id": content_id,
        "content": result.get("content"),
        "visual_brief": result.get("visual_brief"),
        "score": result.get("score"),
        "iterations": result.get("iterations"),
        "task_id": result.get("task_id"),
        "pipeline_log": result.get("pipeline_log"),
        "trace": result.get("trace", {}),
    }


@app.get("/api/experts/{expert_id}/reflections")
async def list_reflections(expert_id: str, user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)
    reflections_dir = Path("data/reflections")
    file_path = reflections_dir / f"{e.get('name', expert_id).lower().replace(' ', '_')}.jsonl"
    if not file_path.exists():
        return {"expert_id": expert_id, "reflections": []}
    reflections = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                reflections.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return {"expert_id": expert_id, "reflections": reflections}


@app.get("/api/experts/{expert_id}/content")
async def get_expert_content(expert_id: str, skip: int = 0, limit: int = 20, user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)
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
    await require_expert_owner(expert_id, user)
    card = ExpertCard(name=e.get("name"), profession=e.get("profession"),
                      expertise=json.loads(e.get("expertise", "[]") or "[]"))
    plan = await generate_content_plan(card, days, api_key=settings.openai_api_key)
    return {"plan": plan}


# ═════════════════════════════════════════════════════════
# SKILLS
# ═════════════════════════════════════════════════════════

_skill_registry: SkillRegistry | None = None

def _get_skill_registry() -> SkillRegistry:
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry(Path(__file__).parent / "content_pipeline" / "agents")
    return _skill_registry


@app.get("/api/skills")
async def list_skills():
    """Returns all available skills grouped by agent."""
    registry = _get_skill_registry()
    return {"skills": registry.list_all()}


@app.get("/api/skills/{agent}/{skill}/evolution")
async def skill_evolution(agent: str, skill: str):
    """Returns evolution log for a specific skill."""
    registry = _get_skill_registry()
    try:
        s = registry.get(agent, skill)
        return {
            "skill": s.name,
            "agent": s.agent,
            "version": s.version,
            "evolution_log": s.evolution_log,
        }
    except KeyError:
        raise HTTPException(404, "Skill not found")


# ═════════════════════════════════════════════════════════
# MEMORY
# ═════════════════════════════════════════════════════════

@app.get("/api/experts/{expert_id}/memory/insights")
async def memory_insights(expert_id: str, user: dict = Depends(get_current_user)):
    """Returns memory insights for an expert."""
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)

    agent = MemoryAgent(data_dir="data/memory")
    reflection = await agent.self_reflection(expert_id)
    return {
        "expert_id": expert_id,
        "reflection": reflection,
    }


@app.get("/api/experts/{expert_id}/memory/gaps")
async def memory_gaps(expert_id: str, user: dict = Depends(get_current_user)):
    """Returns knowledge gaps for an expert."""
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)

    agent = MemoryAgent(data_dir="data/memory")
    gaps = await agent.gap_hunt(expert_id)
    return {
        "expert_id": expert_id,
        "gaps": gaps,
    }


@app.post("/api/experts/{expert_id}/memory/reflect")
async def memory_reflect(expert_id: str, user: dict = Depends(get_current_user)):
    """Triggers self-reflection for an expert's memory."""
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)

    agent = MemoryAgent(data_dir="data/memory")
    reflection = await agent.self_reflection(expert_id)
    return {
        "expert_id": expert_id,
        "reflection": reflection,
    }


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
    await require_expert_owner(expert_id, user)

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
    await require_expert_owner(expert_id, user)
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
    await require_expert_owner(expert_id, user)
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
    # Ownership check: only admin or the expert's owner can view
    expert = await db.expert_get(row.get("expert_id"))
    if not expert:
        raise HTTPException(404, "Export request not found")
    if user.get("role") != "admin" and expert.get("owner_user_id") != user.get("id"):
        raise HTTPException(403, "Нет доступа")
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
    await require_expert_owner(expert_id, user)

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
    # Ownership check: only admin or the expert's owner can view
    expert = await db.expert_get(row.get("expert_id"))
    if not expert:
        raise HTTPException(404, "Deletion request not found")
    if user.get("role") != "admin" and expert.get("owner_user_id") != user.get("id"):
        raise HTTPException(403, "Нет доступа")
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
# SOCIAL INTEGRATIONS
# ═════════════════════════════════════════════════════════

# ── Initialize social publishers ──
_social_publisher: SocialPublisher | None = None

def _get_social_publisher() -> SocialPublisher:
    global _social_publisher
    if _social_publisher is None:
        telegram = None
        if settings.telegram_bot_token:
            telegram = TelegramPoster(settings.telegram_bot_token)
        instagram = None
        if settings.instagram_access_token and settings.instagram_account_id:
            instagram = InstagramPoster(
                settings.instagram_access_token,
                settings.instagram_account_id,
            )
        _social_publisher = SocialPublisher(
            telegram_poster=telegram,
            instagram_poster=instagram,
            db_client=db if settings.supabase_url else None,
        )
    return _social_publisher


@app.post("/api/content/preview", response_model=PreviewResponse)
async def preview_post(
    req: PreviewRequest,
    user: dict = Depends(get_current_user),
):
    """Preview how the post will look on the target platform."""
    publisher = _get_social_publisher()
    return await publisher.preview(PublishRequest(
        expert_id=user.get("id", ""),
        content=req.content,
        platform=req.platform,
        image_url=req.image_url,
        dry_run=True,
    ))


@app.post("/api/content/publish", response_model=PublishResponse)
async def publish_post(
    req: PublishRequest,
    user: dict = Depends(get_current_user),
):
    """Publish generated content to Telegram or Instagram.

    - Pass `dry_run=True` to preview without publishing
    - Provide `channel_id` for Telegram (channel username or ID)
    - Provide `image_url` for Instagram (required)
    - Pass `hashtags` to append at the end
    """
    # Use default channel if none provided
    if req.platform.value == "telegram" and not req.channel_id and settings.default_telegram_channel:
        req.channel_id = settings.default_telegram_channel

    publisher = _get_social_publisher()
    return await publisher.publish(req)


@app.get("/api/content/published")
async def list_published_posts(
    expert_id: str | None = None,
    platform: str | None = None,
    skip: int = 0,
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    """List published posts from history."""
    query = db.table("published_posts").select("*")
    if expert_id:
        query = query.eq("expert_id", expert_id)
    if platform:
        query = query.eq("platform", platform)
    result = await query.order("created_at", desc=True).range(skip, skip + limit - 1).execute()
    posts = result.data if hasattr(result, "data") else []
    return {
        "items": [{**p, "created_at": p.get("created_at")} for p in posts],
        "total": len(posts),
        "skip": skip,
        "limit": limit,
    }


# ═════════════════════════════════════════════════════════
# PAYMENT & SUBSCRIPTIONS
# ═════════════════════════════════════════════════════════

# ── Initialize subscription service ──
_subscription_service: SubscriptionService | None = None

def _get_subscription_service() -> SubscriptionService:
    global _subscription_service
    if _subscription_service is None:
        prodamus = None
        if settings.prodamus_api_key:
            prodamus = ProdamusClient()
        _subscription_service = SubscriptionService(
            db_client=db if settings.supabase_url else None,
            prodamus=prodamus,
        )
    return _subscription_service


@app.post("/api/subscriptions", response_model=SubscriptionResponse)
async def create_subscription(
    req: CreateSubscriptionRequest,
    user: dict = Depends(get_current_user),
):
    """Create a new subscription. Free activates immediately, paid returns payment_url."""
    req.user_id = user.get("id", req.user_id)
    svc = _get_subscription_service()
    return await svc.create_subscription(req)


@app.get("/api/subscriptions/current")
async def get_current_subscription(
    user: dict = Depends(get_current_user),
):
    """Get the current active subscription for the authenticated user."""
    svc = _get_subscription_service()
    sub = await svc.get_subscription(user.get("id", ""))
    if not sub:
        return {"status": "none", "tier": "free", "message": "No subscription found — using free tier"}
    return {
        "id": sub.id,
        "tier": sub.tier,
        "status": sub.status,
        "started_at": sub.started_at,
        "expires_at": sub.expires_at,
        "auto_renew": sub.auto_renew,
    }


@app.post("/api/payment/webhook/prodamus")
async def prodamus_webhook(
    request: Request,
):
    """Receive Prodamus payment webhook."""
    from .payment import ProdamusWebhookPayload

    raw_body = await request.body()
    signature = request.headers.get("X-Signature")

    handler = ProdamusWebhookHandler(settings.prodamus_secret_key)

    # Verify signature if secret is configured
    if settings.prodamus_secret_key:
        if not handler.verify(raw_body, signature):
            logger.warning("Prodamus webhook signature verification failed")
            raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        form = await request.form()
        payload = handler.parse(dict(form))
    except Exception as exc:
        logger.error("Prodamus webhook parse error: %s", exc)
        raise HTTPException(status_code=422, detail="Invalid payload")

    svc = _get_subscription_service()
    success = await svc.handle_webhook(payload)
    if not success:
        raise HTTPException(status_code=400, detail="Webhook processing failed")

    return {"status": "ok"}


@app.get("/api/payment/transactions")
async def list_transactions(
    limit: int = 20,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    """List payment transactions for the authenticated user."""
    result = await db.table("payment_transactions")\
        .select("*")\
        .eq("user_id", user.get("id", ""))\
        .order("created_at", desc=True)\
        .range(skip, skip + limit - 1)\
        .execute()
    rows = result.data if hasattr(result, "data") else []
    return {"items": rows, "total": len(rows), "skip": skip, "limit": limit}


# ═════════════════════════════════════════════════════════
# HEALTH
# ═════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.6.0-payment", "compliance": "152-FZ"}


@app.get("/")
async def root():
    return {"name": "Content Producer API", "version": "0.6.0", "docs": "/docs", "compliance": "152-FZ"}
