from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .interviewer.session import InterviewSession
from .expert_card.card import ExpertCard
from .expert_card.parser import save_card
from .producer_agent.agent import ProducerAgent
from .producer_agent.planner import generate_content_plan
from .content_generator.social_post import generate_social_post
from .content_generator.video_script import generate_video_script
import uuid
from pathlib import Path

app = FastAPI(title="Content Producer", version="0.1.0")

sessions: dict[str, InterviewSession] = {}
cards: dict[str, ExpertCard] = {}

class CreateInterviewRequest(BaseModel):
    expert_name: str

class AnswerRequest(BaseModel):
    answer: str

class GenerateContentRequest(BaseModel):
    expert_id: str
    topic: str
    content_type: str = "post"
    platform: str = "telegram"

@app.post("/api/interview/start")
async def start_interview(req: CreateInterviewRequest):
    session_id = str(uuid.uuid4())
    sessions[session_id] = InterviewSession(expert_name=req.expert_name)
    q = sessions[session_id].get_next_question()
    return {
        "session_id": session_id,
        "question": q.text if q else None,
        "progress": sessions[session_id].get_progress()
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

@app.get("/api/experts")
async def list_experts():
    return {"experts": list(cards.values())}

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
