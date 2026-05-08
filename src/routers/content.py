"""Content generation endpoints."""
import uuid
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from ..config import settings
from ..db_client import db
from ..db.schemas import GenerateContentRequest
from ..dependencies import get_current_user, require_expert_owner
from ..expert_card.card import ExpertCard
from ..content_generator.social_post import generate_social_post
from ..content_generator.video_script import generate_video_script
from ..producer_agent.planner import generate_content_plan
from ..content_pipeline.dispatcher import PipelineDispatcher
from ..content_pipeline.style_adapter import StyleAdapter
from ..content_pipeline.memory_agent import MemoryAgent

router = APIRouter(tags=["content"])


@router.post("/api/experts/{expert_id}/content")
async def generate_content(expert_id: str, req: GenerateContentRequest, user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)
    card = ExpertCard(name=e.get("name"), profession=e.get("profession"),
                      expertise=json.loads(e.get("expertise", "[]") or "[]"))
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


@router.post("/api/experts/{expert_id}/content/v2")
async def generate_content_v2(expert_id: str, req: GenerateContentRequest, user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)
    card = ExpertCard(name=e.get("name"), profession=e.get("profession"),
                      expertise=json.loads(e.get("expertise", "[]") or "[]"))
    card.id = expert_id

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

    adapter = StyleAdapter()
    await adapter.write_to_db(card, db)

    content_id = str(uuid.uuid4())
    await db.content_insert({
        "id": content_id, "expert_id": expert_id, "content_type": req.content_type,
        "topic": req.topic, "platform": req.platform,
        "content": json.dumps({
            "content": result.get("content"), "visual_brief": result.get("visual_brief"),
            "score": result.get("score"), "iterations": result.get("iterations"),
            "task_id": result.get("task_id"), "logs": result.get("logs"),
        }, ensure_ascii=False),
        "creator_user_id": user.get("id"),
        "retention_until": (datetime.now(timezone.utc) + timedelta(days=settings.default_retention_days)).isoformat(),
    })
    return {
        "content_id": content_id, "content": result.get("content"),
        "visual_brief": result.get("visual_brief"), "score": result.get("score"),
        "iterations": result.get("iterations"), "task_id": result.get("task_id"),
        "pipeline_log": result.get("pipeline_log"), "trace": result.get("trace", {}),
    }


@router.get("/api/experts/{expert_id}/content")
async def get_expert_content(expert_id: str, skip: int = 0, limit: int = 20, user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)
    items = await db.content_list(expert_id, skip, limit)
    return {"items": [{"id": i.get("id"), "type": i.get("content_type"),
                       "topic": i.get("topic"), "platform": i.get("platform"),
                       "status": i.get("status"), "created_at": i.get("created_at")}
                      for i in items]}


@router.get("/api/experts/{expert_id}/reflections")
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


@router.post("/api/experts/{expert_id}/plan")
async def get_content_plan(expert_id: str, days: int = 7, user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)
    card = ExpertCard(name=e.get("name"), profession=e.get("profession"),
                      expertise=json.loads(e.get("expertise", "[]") or "[]"))
    plan = await generate_content_plan(card, days, api_key=settings.openai_api_key)
    return {"plan": plan}


@router.get("/api/experts/{expert_id}/memory/insights")
async def memory_insights(expert_id: str, user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)
    agent = MemoryAgent(data_dir="data/memory")
    reflection = await agent.self_reflection(expert_id)
    return {"expert_id": expert_id, "reflection": reflection}


@router.get("/api/experts/{expert_id}/memory/gaps")
async def memory_gaps(expert_id: str, user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)
    agent = MemoryAgent(data_dir="data/memory")
    gaps = await agent.gap_hunt(expert_id)
    return {"expert_id": expert_id, "gaps": gaps}


@router.post("/api/experts/{expert_id}/memory/reflect")
async def memory_reflect(expert_id: str, user: dict = Depends(get_current_user)):
    e = await db.expert_get(expert_id)
    if not e:
        raise HTTPException(404, "Expert not found")
    await require_expert_owner(expert_id, user)
    agent = MemoryAgent(data_dir="data/memory")
    reflection = await agent.self_reflection(expert_id)
    return {"expert_id": expert_id, "reflection": reflection}
