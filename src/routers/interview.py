"""Interview endpoints."""
import uuid
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from ..config import settings
from ..db_client import db
from ..db.schemas import InterviewStartRequest, InterviewAnswerRequest
from ..dependencies import get_current_user
from ..interviewer.questions import QUESTION_BANK
from ..interviewer.analyzer import analyze_interview
from ..expert_card.parser import save_card
from ..api_helpers import active_interviews

router = APIRouter(prefix="/api/interview", tags=["interview"])


@router.post("/start")
async def start_interview(req: InterviewStartRequest, user: dict = Depends(get_current_user)):
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    retention = (datetime.now(timezone.utc) + timedelta(days=settings.interview_retention_days)).isoformat()
    await db.interview_insert({
        "id": session_id, "expert_name": req.expert_name,
        "creator_user_id": user.get("id"), "retention_until": retention,
        "created_at": now, "responses": json.dumps({}), "is_complete": False,
    })

    active_interviews[session_id] = {
        "expert_name": req.expert_name, "responses": {},
        "asked_questions": [], "current_category": "personality", "is_complete": False,
    }

    cat = "personality"
    available = [q for q in QUESTION_BANK if q.block == cat]
    q_text = available[0].text if available else None

    return {"session_id": session_id, "question": q_text,
            "progress": {"answered": 0, "total": len(QUESTION_BANK), "percent": 0}}


@router.post("/{session_id}/answer")
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
    return {"question": next_q_text, "is_complete": data["is_complete"],
            "progress": {"answered": answered, "total": total,
                         "percent": round(answered / total * 100) if total else 0}}


@router.post("/{session_id}/finalize")
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
        "id": expert_id, "name": card.name or data["expert_name"],
        "nickname": card.nickname, "profession": card.profession,
        "expertise": card.expertise if isinstance(card.expertise, list) else card.expertise,
        "uvp": card.uvp,
        "tone_style": card.tone.style if card.tone else "",
        "tone_format_pref": card.tone.format_pref if card.tone else "",
        "tone_emoji_style": card.tone.emoji_style if card.tone else "",
        "stories": json.dumps(card.stories) if isinstance(card.stories, list) else card.stories,
        "achievements": json.dumps(card.achievements) if isinstance(card.achievements, list) else card.achievements,
        "consent_granted": True, "consent_granted_at": now,
        "consent_version": settings.minimum_consent_version,
        "owner_user_id": user.get("id"), "retention_until": retention, "created_at": now,
    })

    experts_dir = Path("experts")
    experts_dir.mkdir(exist_ok=True)
    safe_name = (card.name or data["expert_name"]).lower().replace(" ", "_").replace("/", "_")
    save_path = experts_dir / f"{safe_name}.md"
    save_card(card, save_path)

    del active_interviews[session_id]
    return {"expert_id": expert_id, "card": card.model_dump(), "saved_to": str(save_path)}
