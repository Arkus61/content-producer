"""Full transcription pipeline: file/URL -> transcribed text."""
import tempfile
from pathlib import Path
import asyncio

from .audio import extract_audio, validate_file
from .youtube import download_youtube_audio, is_youtube_url
from .whisper import transcribe_audio

async def transcribe_from_file(
    file_path: str | Path,
    api_key: str,
    language: str = "ru",
) -> str:
    """Transcribe from local audio/video file."""
    path = Path(file_path)
    if not validate_file(path):
        raise ValueError(f"Unsupported file type: {path.suffix}")
    
    # If it's a video, extract audio first
    audio_path = path
    if path.suffix.lower() in {".mp4", ".webm", ".mkv", ".avi", ".mov"}:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_path = extract_audio(path, tmp.name)
    
    try:
        text = await transcribe_audio(audio_path, api_key, language)
    finally:
        # Clean up extracted file if different from input
        if audio_path != path and Path(audio_path).exists():
            Path(audio_path).unlink()
    
    return text

async def transcribe_from_youtube(
    youtube_url: str,
    api_key: str,
    language: str = "ru",
) -> str:
    """Download YouTube video audio and transcribe."""
    if not is_youtube_url(youtube_url):
        raise ValueError(f"Not a YouTube URL: {youtube_url}")
    
    audio_path = download_youtube_audio(youtube_url)
    
    try:
        text = await transcribe_audio(audio_path, api_key, language)
    finally:
        if audio_path.exists():
            audio_path.unlink()
    
    return text

async def transcribe(
    source: str,
    source_type: str,  # "file" or "youtube"
    api_key: str,
    language: str = "ru",
) -> str:
    """Unified transcribe entry point."""
    if source_type == "file":
        return await transcribe_from_file(source, api_key, language)
    elif source_type == "youtube":
        return await transcribe_from_youtube(source, api_key, language)
    else:
        raise ValueError(f"Unknown source type: {source_type}")
