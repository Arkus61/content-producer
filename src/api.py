from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from .interviewer.session import InterviewSession
from .expert_card.card import ExpertCard
from .expert_card.parser import save_card
from .producer_agent.agent import ProducerAgent
from .producer_agent.planner import generate_content_plan
from .content_generator.social_post import generate_social_post
from .content_generator.video_script import generate_video_script
from .transcriber.pipeline import transcribe
from .transcriber.youtube import is_youtube_url
import uuid
import tempfile
from pathlib import Path
from datetime import datetime

app = FastAPI(title="Content Producer", version="0.1.0")

sessions: dict[str, InterviewSession] = {}
cards: dict[str, ExpertCard] = {}
transcriptions: dict[str, dict] = {}

class CreateInterviewRequest(BaseModel):
    expert_name: str

class AnswerRequest(BaseModel):
    answer: str

class GenerateContentRequest(BaseModel):
    expert_id: str
    topic: str
    content_type: str = "post"
    platform: str = "telegram"

class YoutubeTranscribeRequest(BaseModel):
    expert_name: str
    youtube_url: str
    language: str = "ru"

# ── Interview endpoints ──────────────────────────────────────

@app.post("/api/interview/start")
async def start_interview(req: CreateInterviewRequest):
    session_id = str(uuid.uuid4())
    sessions[session_id] = InterviewSession(expert_name=req.expert_name)
    q = sessions[session_id].get_next_question()
    return {
        "session_id": session_id,
        "question": q.text if q else None,
        "progress": sessions[session_id].get_progress(),
    }

@app.post("/api/interview/{session_id}/answer")
async def submit_answer(session_id: str, req: AnswerRequest):
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")
    session = sessions[session_id]
    if session.is_complete:
        return {"message": "Interview already complete"}
    q = session.get_next_question()
    if q:
        session.add_response(q.id, req.answer)
    next_q = session.get_next_question()
    return {
        "question": next_q.text if next_q else None,
        "is_complete": session.is_complete,
        "progress": session.get_progress(),
    }

# ── Audio/Video transcription endpoints ──────────────────────

@app.post("/api/transcribe/youtube")
async def transcribe_youtube(req: YoutubeTranscribeRequest):
    """Transcribe YouTube video and extract expert info."""
    from .config import settings
    
    if not settings.openai_api_key:
        raise HTTPException(500, "OPENAI_API_KEY not configured")
    
    if not is_youtube_url(req.youtube_url):
        raise HTTPException(400, "Not a valid YouTube URL")
    
    try:
        text = await transcribe(req.youtube_url, "youtube", settings.openai_api_key, req.language)
    except Exception as e:
        raise HTTPException(500, f"Transcription failed: {str(e)}")
    
    transcription_id = str(uuid.uuid4())
    transcriptions[transcription_id] = {
        "expert_name": req.expert_name,
        "source": req.youtube_url,
        "text": text,
        "created_at": datetime.now().isoformat(),
    }
    
    return {
        "transcription_id": transcription_id,
        "expert_name": req.expert_name,
        "text_length": len(text),
        "preview": text[:500],
    }

@app.post("/api/transcribe/upload")
async def transcribe_upload(
    expert_name: str = Form(...),
    file: UploadFile = File(...),
    language: str = Form("ru"),
):
    """Upload audio/video file and transcribe it."""
    from .config import settings
    
    if not settings.openai_api_key:
        raise HTTPException(500, "OPENAI_API_KEY not configured")
    
    # Save uploaded file temporarily
    suffix = Path(file.filename).suffix if file.filename else ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        text = await transcribe(tmp_path, "file", settings.openai_api_key, language)
    except Exception as e:
        raise HTTPException(500, f"Transcription failed: {str(e)}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    
    transcription_id = str(uuid.uuid4())
    transcriptions[transcription_id] = {
        "expert_name": expert_name,
        "source": file.filename or "upload",
        "text": text,
        "created_at": datetime.now().isoformat(),
    }
    
    return {
        "transcription_id": transcription_id,
        "expert_name": expert_name,
        "text_length": len(text),
        "preview": text[:500],
    }

@app.get("/api/transcribe/{transcription_id}")
async def get_transcription(transcription_id: str):
    """Get full transcription text."""
    if transcription_id not in transcriptions:
        raise HTTPException(404, "Transcription not found")
    return transcriptions[transcription_id]

@app.post("/api/transcribe/{transcription_id}/to-card")
async def transcription_to_card(transcription_id: str):
    """Convert transcription text into an Expert Card."""
    from .interviewer.analyzer import analyze_interview
    from .config import settings
    
    if transcription_id not in transcriptions:
        raise HTTPException(404, "Transcription not found")
    
    transcription = transcriptions[transcription_id]
    text = transcription["text"]
    expert_name = transcription["expert_name"]
    
    # Create a pseudo-session to feed into the analyzer
    session = InterviewSession(expert_name=expert_name)
    session.add_response("transcription_full", text)
    session.is_complete = True
    
    try:
        card = await analyze_interview(session, settings.openai_api_key)
    except Exception as e:
        raise HTTPException(500, f"Card analysis failed: {str(e)}")
    
    # Save card
    expert_id = str(uuid.uuid4())
    cards[expert_id] = card
    
    experts_dir = Path("experts")
    experts_dir.mkdir(exist_ok=True)
    save_path = experts_dir / f"{expert_name.replace(' ', '_')}.md"
    save_card(card, save_path)
    
    return {
        "expert_id": expert_id,
        "card": card.model_dump(),
        "saved_to": str(save_path),
    }

# ── Experts & Content endpoints ──────────────────────────────

@app.get("/api/experts")
async def list_experts():
    return {"experts": [
        {"id": eid, "name": c.name, "profession": c.profession}
        for eid, c in cards.items()
    ]}

@app.post("/api/experts/{expert_id}/content")
async def generate_content(expert_id: str, req: GenerateContentRequest):
    if expert_id not in cards:
        raise HTTPException(404, "Expert not found")
    card = cards[expert_id]
    if req.content_type == "post":
        content = await generate_social_post(card, req.topic, req.platform)
    elif req.content_type == "video":
        content = await generate_video_script(card, req.topic)
    else:
        raise HTTPException(400, "Unknown content type")
    return {"content": content}

@app.post("/api/experts/{expert_id}/plan")
async def get_content_plan(expert_id: str, days: int = 7):
    if expert_id not in cards:
        raise HTTPException(404, "Expert not found")
    plan = generate_content_plan(cards[expert_id], days)
    return {"plan": plan}

@app.get("/api/experts/{expert_id}")
async def get_expert(expert_id: str):
    if expert_id not in cards:
        raise HTTPException(404, "Expert not found")
    return cards[expert_id]
