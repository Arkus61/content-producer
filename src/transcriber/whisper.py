"""Transcription via OpenAI Whisper API."""
import openai
from pathlib import Path

async def transcribe_audio(
    audio_path: str | Path,
    api_key: str,
    language: str = "ru",
) -> str:
    """Transcribe audio file using OpenAI Whisper API."""
    client = openai.AsyncOpenAI(api_key=api_key)
    
    with open(audio_path, "rb") as f:
        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language=language,
            response_format="text",
        )
    
    return response.strip()

async def transcribe_audio_with_timestamps(
    audio_path: str | Path,
    api_key: str,
    language: str = "ru",
) -> dict:
    """Transcribe with verbose_json to get timestamps for each segment."""
    client = openai.AsyncOpenAI(api_key=api_key)
    
    with open(audio_path, "rb") as f:
        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language=language,
            response_format="verbose_json",
            timestamp_granularities=["segments"],
        )
    
    return {
        "text": response.text,
        "segments": [
            {
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
            }
            for seg in response.segments
        ]
    }
