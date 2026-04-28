"""YouTube video download via yt-dlp."""
import subprocess
from pathlib import Path
from uuid import uuid4

YT_TMP_DIR = Path("temp/youtube")

def download_youtube_audio(url: str, output_dir: Path = None) -> Path:
    """Download audio from YouTube video URL."""
    if output_dir is None:
        output_dir = YT_TMP_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_template = str(output_dir / f"{uuid4().hex}")
    
    cmd = [
        "yt-dlp",
        "-x",                         # extract audio
        "--audio-format", "wav",
        "--audio-quality", "5",       # medium quality
        "-o", output_template,
        "--no-playlist",
        "--socket-timeout", "30",
        url,
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp error: {result.stderr}")
    
    # Find the downloaded file
    wav_files = list(output_dir.glob("*.wav"))
    if not wav_files:
        raise RuntimeError("yt-dlp: no output file found")
    
    return wav_files[-1]

def is_youtube_url(url: str) -> bool:
    """Check if URL points to YouTube."""
    return any(host in url.lower() for host in [
        "youtube.com", "youtu.be", "youtube-nocookie.com",
    ])
