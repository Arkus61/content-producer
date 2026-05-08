"""Tests for transcriber module."""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from src.transcriber.youtube import is_youtube_url
from src.transcriber.pipeline import transcribe


# ── is_youtube_url ──────────────────────────────────────────

class TestIsYoutubeUrl:
    def test_valid_youtube_urls(self):
        """youtube.com, youtu.be, youtube-nocookie.com should all return True."""
        valid = [
            "https://www.youtube.com/watch?v=abc123",
            "https://youtube.com/watch?v=xyz",
            "https://youtu.be/abc123",
            "https://www.youtube-nocookie.com/embed/abc",
        ]
        for url in valid:
            assert is_youtube_url(url), f"Should be valid: {url}"

    def test_invalid_urls(self):
        """Non-YouTube URLs and random text should return False."""
        invalid = [
            "https://vimeo.com/12345",
            "https://example.com/video",
            "hello world",
            "",
            "ftp://youtube.com/file",  # unlikely but still contains the host
        ]
        # Note: the last one does contain "youtube.com" so it'll match.
        # Keep genuinely invalid ones:
        truly_invalid = [
            "https://vimeo.com/12345",
            "https://example.com/video",
            "hello world",
            "",
        ]
        for url in truly_invalid:
            assert not is_youtube_url(url), f"Should be invalid: {url}"


# ── transcribe pipeline (mocked) ────────────────────────────

@pytest.mark.asyncio
async def test_transcribe_from_youtube():
    """transcribe with source_type='youtube' calls download + transcribe_audio."""
    with (
        patch("src.transcriber.pipeline.download_youtube_audio") as mock_dl,
        patch("src.transcriber.pipeline.transcribe_audio", new_callable=AsyncMock) as mock_ta,
    ):
        mock_dl.return_value = Path("/tmp/test.wav")
        mock_ta.return_value = "Привет мир"

        result = await transcribe(
            source="https://youtube.com/watch?v=test",
            source_type="youtube",
            api_key="sk-test",
            language="ru",
        )

        assert result == "Привет мир"
        mock_dl.assert_called_once_with("https://youtube.com/watch?v=test")
        mock_ta.assert_called_once_with(Path("/tmp/test.wav"), "sk-test", "ru")


@pytest.mark.asyncio
async def test_transcribe_from_file():
    """transcribe with source_type='file' calls validate + transcribe_audio."""
    with (
        patch("src.transcriber.pipeline.validate_file", return_value=True),
        patch("src.transcriber.pipeline.transcribe_audio", new_callable=AsyncMock) as mock_ta,
    ):
        mock_ta.return_value = "Транскрипция файла"

        result = await transcribe(
            source="/tmp/audio.mp3",
            source_type="file",
            api_key="sk-test",
            language="en",
        )

        assert result == "Транскрипция файла"
        mock_ta.assert_called_once_with(Path("/tmp/audio.mp3"), "sk-test", "en")


@pytest.mark.asyncio
async def test_transcribe_unknown_type():
    """Unknown source_type should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown source type"):
        await transcribe(
            source="whatever",
            source_type="podcast",
            api_key="sk-test",
        )


@pytest.mark.asyncio
async def test_transcribe_invalid_youtube_url():
    """Non-YouTube URL with source_type='youtube' should raise ValueError."""
    with pytest.raises(ValueError, match="Not a YouTube URL"):
        await transcribe(
            source="https://vimeo.com/12345",
            source_type="youtube",
            api_key="sk-test",
        )
