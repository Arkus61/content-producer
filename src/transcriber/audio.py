"""Audio extraction from video files."""
import subprocess
from pathlib import Path

ALLOWED_EXTENSIONS = {".mp3", ".mp4", ".wav", ".webm", ".m4a", ".ogg", ".flac", ".mkv", ".avi", ".mov"}

def extract_audio(input_path: str | Path, output_path: str | Path = None) -> Path:
    """Extract audio from video file using ffmpeg."""
    input_path = Path(input_path)
    if output_path is None:
        output_path = input_path.with_suffix(".wav")
    output_path = Path(output_path)
    
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vn",           # no video
        "-acodec", "pcm_s16le",
        "-ar", "16000",  # Whisper prefers 16kHz
        "-ac", "2",
        str(output_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error: {result.stderr}")
    
    return output_path

def validate_file(path: str | Path) -> bool:
    """Check if file extension is supported."""
    return Path(path).suffix.lower() in ALLOWED_EXTENSIONS
