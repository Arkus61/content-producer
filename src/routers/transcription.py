"""Transcription endpoints."""
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from ..config import settings
from ..db_client import db
from ..dependencies import get_current_user
from ..transcriber.pipeline import transcribe
from ..transcriber.youtube import is_youtube_url

router = APIRouter(tags=["transcription"])


@router.post("/api/transcribe/youtube")
async def transcribe_youtube(
    expert_name: str, youtube_url: str, language: str = "ru",
    expert_id: str | None = None, user: dict = Depends(get_current_user),
):
    if not settings.openai_api_key:
        raise HTTPException(500, "OPENAI_API_KEY not configured")
    if not is_youtube_url(youtube_url):
        raise HTTPException(400, "Not a valid YouTube URL")

    text = await transcribe(youtube_url, "youtube", settings.openai_api_key, language)
    tid = str(uuid.uuid4())
    await db.transcription_insert({
        "id": tid, "expert_id": expert_id, "source_url": youtube_url,
        "source_type": "youtube", "text": text, "language": language,
        "creator_user_id": user.get("id"),
        "retention_until": (datetime.now(timezone.utc) + timedelta(days=settings.transcription_retention_days)).isoformat(),
    })
    return {"transcription_id": tid, "expert_name": expert_name, "text_length": len(text), "preview": text[:300]}


@router.post("/api/transcribe/upload")
async def transcribe_upload(
    expert_name: str = Form(...), file: UploadFile = File(...),
    language: str = Form("ru"), expert_id: str | None = Form(None),
    user: dict = Depends(get_current_user),
):
    if not settings.openai_api_key:
        raise HTTPException(500, "OPENAI_API_KEY not configured")
    import tempfile
    import logging
    logger = logging.getLogger("content-producer")
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


@router.get("/api/transcribe/{transcription_id}")
async def get_transcription(transcription_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") == "admin":
        t = await db.transcription_get(transcription_id)
    else:
        trans = await db.transcription_list(expert_id=None, creator_user_id=user.get("id"))
        t = next((x for x in trans if x.get("id") == transcription_id), None)
    if not t:
        raise HTTPException(404, "Transcription not found")
    return {"id": t.get("id"), "expert_id": t.get("expert_id"),
            "source_url": t.get("source_url"), "text": t.get("text"),
            "language": t.get("language"), "created_at": t.get("created_at")}
