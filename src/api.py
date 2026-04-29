import logging
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db.engine import async_engine as engine, async_session_factory as async_session
from .db.models import Base, ExpertCardModel, InterviewSessionModel, TranscriptionModel, ContentItemModel
from .db.schemas import (
    ExpertCardCreate, ExpertCardResponse,
    InterviewStartRequest, InterviewAnswerRequest,
    GenerateContentRequest, TranscriptionResponse, ContentPlanResponse,
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

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("content-producer")

# ── In-memory interview sessions (short-lived) ────────────
active_interviews: dict[str, dict] = {}

# ── Lifespan ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if not exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")
    yield
    # Shutdown
    await engine.dispose()
    logger.info("Database engine disposed")

# ── App ───────────────────────────────────────────────────
app = FastAPI(
    title="Content Producer API",
    version="0.2.0",
    description="AI SaaS for expert content creation",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(",") if settings.cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Helpers ───────────────────────────────────────────────
def _to_expert_card_response(model: ExpertCardModel) -> dict:
    return {
        "id": model.id,
        "name": model.name,
        "nickname": model.nickname,
        "profession": model.profession,
        "expertise": json.loads(model.expertise) if model.expertise else [],
        "uvp": model.uvp,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }

def _get_card_for_api(id: str) -> ExpertCard:
    """Load ExpertCard from DB for AI generation calls."""
    from .expert_card.card import ToneOfVoice, Audience, ContentStrategy
    # For now, create a minimal card — full impl reads from DB models
    return ExpertCard(name="expert", expertise=[], tone=ToneOfVoice())

# ── Health / Info ─────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}

@app.get("/")
async def root():
    return {
        "name": "Content Producer API",
        "version": "0.2.0",
        "docs": "/docs",
    }

# ── Interview Endpoints ───────────────────────────────────
@app.post("/api/interview/start")
async def start_interview(req: InterviewStartRequest):
    session_id = str(uuid.uuid4())
    
    db_session = InterviewSessionModel(
        id=session_id,
        expert_name=req.expert_name,
    )
    async with async_session() as s:
        s.add(db_session)
        await s.commit()
    
    active_interviews[session_id] = {
        "expert_name": req.expert_name,
        "responses": {},
        "asked_questions": [],
        "current_category": "personality",
        "is_complete": False,
    }
    
    # Get first question
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
    
    # Find current question
    asked = set(data["asked_questions"])
    available = [q for q in QUESTION_BANK if q.block == data["current_category"] and q.id not in asked]
    if available:
        q = available[0]
        data["responses"][q.id] = req.answer
        data["asked_questions"].append(q.id)
    
    # Move to next question
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
        "progress": {
            "answered": answered,
            "total": total,
            "percent": round(answered / total * 100),
        },
    }

@app.post("/api/interview/{session_id}/finalize")
async def finalize_interview(session_id: str):
    if session_id not in active_interviews:
        raise HTTPException(404, "Interview session not found")
    
    data = active_interviews[session_id]
    
    # Create Analyzable session-like object
    class _Session:
        def __init__(self, d):
            self.expert_name = d["expert_name"]
            self.responses = d["responses"]
            self.asked_questions = list(d["responses"].keys())
            self.is_complete = True
    
    session = _Session(data)
    
    card = await analyze_interview(session, settings.openai_api_key)
    
    expert_id = str(uuid.uuid4())
    db_card = ExpertCardModel(
        id=expert_id,
        name=card.name,
        nickname=card.nickname,
        profession=card.profession,
        expertise=json.dumps(card.expertise),
        uvp=card.uvp,
        tone_of_voice=json.dumps(card.tone.model_dump()),
        audience=json.dumps(card.audience.model_dump()),
        strategy=json.dumps(card.strategy.model_dump()),
        stories=json.dumps(card.stories),
        achievements=json.dumps(card.achievements),
    )
    
    async with async_session() as s:
        s.add(db_card)
        await s.commit()
    
    # Save local .md
    experts_dir = Path("experts")
    experts_dir.mkdir(exist_ok=True)
    save_path = experts_dir / f"{card.name.lower().replace(' ', '_')}.md"
    save_card(card, save_path)
    
    del active_interviews[session_id]
    
    return {
        "expert_id": expert_id,
        "card": card.model_dump(),
        "saved_to": str(save_path),
    }

# ── Transcription Endpoints ──────────────────────────────
@app.post("/api/transcribe/youtube")
async def transcribe_youtube(expert_name: str, youtube_url: str, language: str = "ru"):
    if not settings.openai_api_key:
        raise HTTPException(500, "OPENAI_API_KEY not configured")
    
    if not is_youtube_url(youtube_url):
        raise HTTPException(400, "Not a valid YouTube URL")
    
    try:
        text = await transcribe(youtube_url, "youtube", settings.openai_api_key, language)
    except Exception as e:
        logger.exception("Transcription failed")
        raise HTTPException(500, f"Transcription failed: {str(e)}")
    
    transcription_id = str(uuid.uuid4())
    db_trans = TranscriptionModel(
        id=transcription_id,
        expert_id=None,
        source_url=youtube_url,
        source_type="youtube",
        text=text,
        language=language,
    )
    
    async with async_session() as s:
        s.add(db_trans)
        await s.commit()
    
    return {
        "transcription_id": transcription_id,
        "expert_name": expert_name,
        "text_length": len(text),
        "preview": text[:300],
    }

@app.post("/api/transcribe/upload")
async def transcribe_upload(
    expert_name: str = Form(...),
    file: UploadFile = File(...),
    language: str = Form("ru"),
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
        raise HTTPException(500, f"Transcription failed: {str(e)}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    
    transcription_id = str(uuid.uuid4())
    db_trans = TranscriptionModel(
        id=transcription_id,
        expert_id=None,
        source_url=file.filename or "upload",
        source_type="file",
        text=text,
        language=language,
    )
    
    async with async_session() as s:
        s.add(db_trans)
        await s.commit()
    
    return {
        "transcription_id": transcription_id,
        "expert_name": expert_name,
        "text_length": len(text),
        "preview": text[:300],
    }

@app.get("/api/transcribe/{transcription_id}")
async def get_transcription(transcription_id: str):
    async with async_session() as s:
        result = await s.execute(
            select(TranscriptionModel).where(TranscriptionModel.id == transcription_id)
        )
        t = result.scalar_one_or_none()
    
    if not t:
        raise HTTPException(404, "Transcription not found")
    
    return {
        "id": t.id,
        "expert_id": t.expert_id,
        "source_url": t.source_url,
        "text": t.text,
        "language": t.language,
        "created_at": t.created_at,
    }

@app.post("/api/transcribe/{transcription_id}/to-card")
async def transcription_to_card(transcription_id: str):
    async with async_session() as s:
        result = await s.execute(
            select(TranscriptionModel).where(TranscriptionModel.id == transcription_id)
        )
        t = result.scalar_one_or_none()
    
    if not t:
        raise HTTPException(404, "Transcription not found")
    
    # Create pseudo-session for analyzer
    class _Session:
        def __init__(self, txt, name):
            self.expert_name = name
            self.responses = {"transcription": txt}
            self.asked_questions = ["transcription"]
            self.is_complete = True
    
    session = _Session(t.text, t.expert_id or "unknown")
    card = await analyze_interview(session, settings.openai_api_key)
    
    expert_id = str(uuid.uuid4())
    db_card = ExpertCardModel(
        id=expert_id,
        name=card.name,
        nickname=card.nickname,
        profession=card.profession,
        expertise=json.dumps(card.expertise),
        uvp=card.uvp,
        tone_of_voice=json.dumps(card.tone.model_dump()),
        audience=json.dumps(card.audience.model_dump()),
        strategy=json.dumps(card.strategy.model_dump()),
        stories=json.dumps(card.stories),
    )
    
    async with async_session() as s:
        s.add(db_card)
        t.expert_id = expert_id
        await s.commit()
    
    experts_dir = Path("experts")
    experts_dir.mkdir(exist_ok=True)
    save_card(card, experts_dir / f"{card.name.lower().replace(' ', '_')}.md")
    
    return {
        "expert_id": expert_id,
        "card": card.model_dump(),
    }

# ── Experts & Content Endpoints ───────────────────────────
@app.get("/api/experts")
async def list_experts(skip: int = 0, limit: int = 50):
    async with async_session() as s:
        result = await s.execute(
            select(ExpertCardModel).order_by(ExpertCardModel.created_at.desc()).offset(skip).limit(limit)
        )
        experts = result.scalars().all()
    
    return {"experts": [_to_expert_card_response(e) for e in experts]}

@app.get("/api/experts/{expert_id}")
async def get_expert(expert_id: str):
    async with async_session() as s:
        result = await s.execute(select(ExpertCardModel).where(ExpertCardModel.id == expert_id))
        e = result.scalar_one_or_none()
    
    if not e:
        raise HTTPException(404, "Expert not found")
    
    return _to_expert_card_response(e)

@app.post("/api/experts")
async def create_expert(req: ExpertCardCreate):
    expert_id = str(uuid.uuid4())
    db_card = ExpertCardModel(
        id=expert_id,
        name=req.name,
        nickname=req.nickname,
        profession=req.profession,
        expertise=json.dumps(req.expertise),
        uvp=req.uvp,
    )
    
    async with async_session() as s:
        s.add(db_card)
        await s.commit()
    
    return {"expert_id": expert_id}

@app.delete("/api/experts/{expert_id}")
async def delete_expert(expert_id: str):
    async with async_session() as s:
        result = await s.execute(select(ExpertCardModel).where(ExpertCardModel.id == expert_id))
        e = result.scalar_one_or_none()
        if not e:
            raise HTTPException(404, "Expert not found")
        await s.delete(e)
        await s.commit()
    
    return {"deleted": True}

@app.post("/api/experts/{expert_id}/content")
async def generate_content(expert_id: str, req: GenerateContentRequest):
    async with async_session() as s:
        result = await s.execute(select(ExpertCardModel).where(ExpertCardModel.id == expert_id))
        e = result.scalar_one_or_none()
    
    if not e:
        raise HTTPException(404, "Expert not found")
    
    card = ExpertCard(
        name=e.name,
        profession=e.profession,
        expertise=json.loads(e.expertise),
        tone=json.loads(e.tone_of_voice) if e.tone_of_voice else {},
    )
    
    if req.content_type == "post":
        content = await generate_social_post(card, req.topic, req.platform, settings.openai_api_key)
    elif req.content_type == "video":
        content = await generate_video_script(card, req.topic, api_key=settings.openai_api_key)
    else:
        raise HTTPException(400, "Unsupported content type")
    
    # Save to DB
    content_id = str(uuid.uuid4())
    body_text = content if isinstance(content, str) else json.dumps(content)
    db_content = ContentItemModel(
        id=content_id,
        expert_id=expert_id,
        content_type=req.content_type,
        topic=req.topic,
        platform=req.platform,
        content=body_text,
    )
    
    async with async_session() as s:
        s.add(db_content)
        await s.commit()
    
    return {"content_id": content_id, "content": content}

@app.get("/api/experts/{expert_id}/content")
async def get_expert_content(expert_id: str, skip: int = 0, limit: int = 20):
    async with async_session() as s:
        result = await s.execute(
            select(ContentItemModel)
            .where(ContentItemModel.expert_id == expert_id)
            .order_by(ContentItemModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items = result.scalars().all()
    
    return {
        "items": [
            {
                "id": i.id,
                "type": i.content_type,
                "topic": i.topic,
                "platform": i.platform,
                "status": i.status,
                "created_at": i.created_at,
            }
            for i in items
        ]
    }

@app.post("/api/experts/{expert_id}/plan")
async def get_content_plan(expert_id: str, days: int = 7):
    async with async_session() as s:
        result = await s.execute(select(ExpertCardModel).where(ExpertCardModel.id == expert_id))
        e = result.scalar_one_or_none()
    
    if not e:
        raise HTTPException(404, "Expert not found")
    
    card = ExpertCard(name=e.name, profession=e.profession, expertise=json.loads(e.expertise))
    plan = generate_content_plan(card, days)
    
    return {"plan": plan}
