"""Preview generator — show how a post will look on a platform."""
from __future__ import annotations

import re
import html
from typing import Optional
from .models import PreviewRequest, PreviewResponse, Platform

_READ_SPEED_WPS = 200  # words per minute average reading speed


class PreviewGenerator:
    """Generates platform-native previews without actual publishing."""

    def generate(self, req: PreviewRequest) -> PreviewResponse:
        """Create a realistic preview of the post."""
        text = req.content
        platform = req.platform
        warnings: list[str] = []
        truncated = False

        # Platform-specific processing
        if platform == Platform.telegram:
            rendered, truncated, warnings = self._render_telegram(text, req.max_length)
        elif platform == Platform.instagram:
            rendered, truncated, warnings = self._render_instagram(text, req.max_length)
        else:
            rendered = text

        char_count = len(rendered)
        line_count = rendered.count("\n") + 1
        word_count = len(re.findall(r"\b\w+\b", rendered))
        read_time = max(1, round(word_count / (_READ_SPEED_WPS / 60)))

        return PreviewResponse(
            platform=platform.value,
            rendered_text=rendered,
            truncated=truncated,
            char_count=char_count,
            line_count=line_count,
            estimated_read_time_sec=read_time,
            image_preview_url=req.image_url,
            warnings=warnings,
        )

    def _render_telegram(self, text: str, max_len: int = 4096) -> tuple[str, bool, list[str]]:
        """Render preview for Telegram (HTML-like display)."""
        warnings: list[str] = []
        truncated = False

        # Telegram supports **bold**, __italic__, `code`, ```code blocks```
        # Strip unsupported markdown to HTML conversion for preview
        text = html.escape(text)

        # Convert simple markdown to visual cues
        text = re.sub(r"\*\*(.+?)\*\*", r"\033[1m\1\033[0m", text)  # bold marker
        text = re.sub(r"__(.+?)__", r"\033[3m\1\033[0m", text)  # italic marker
        text = re.sub(r"`(.+?)`", r"`\1`", text)  # keep inline code as-is

        # Truncate if exceeds Telegram limit
        if len(text) > max_len:
            text = text[:max_len - 3] + "..."
            truncated = True
            warnings.append(f"Text exceeds Telegram limit ({max_len} chars), truncated")

        # Check for link previews
        url_count = len(re.findall(r"https?://\S+", text))
        if url_count > 0:
            warnings.append(f"{url_count} URL(s) detected — Telegram may generate link preview")

        return text, truncated, warnings

    def _render_instagram(self, text: str, max_len: int = 2200) -> tuple[str, bool, list[str]]:
        """Render preview for Instagram caption format."""
        warnings: list[str] = []
        truncated = False

        # Count hashtags
        hashtags = re.findall(r"#\w+", text)
        unique_hashtags = list(set(hashtags))
        if len(unique_hashtags) > 30:
            warnings.append(f"Too many hashtags ({len(unique_hashtags)}), Instagram allows max 30")

        # Instagram doesn't support bold/italic markdown — strip formatting markers
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"```[\s\S]*?```", "", text)  # remove code blocks entirely
        text = re.sub(r"`(.+?)`", r"\1", text)  # remove inline code markers

        # Truncate
        if len(text) > max_len:
            text = text[:max_len - 3] + "..."
            truncated = True
            warnings.append(f"Text exceeds Instagram limit ({max_len} chars), truncated")

        # Check mention count
        mentions = re.findall(r"@\w+", text)
        if len(mentions) > 20:
            warnings.append(f"Too many mentions ({len(mentions)}), consider reducing")

        # First line is visible without "...more"
        lines = text.split("\n")
        first_line = lines[0] if lines else ""
        if len(first_line) < 20:
            warnings.append("First line is very short — front-load emotion/hook for Instagram")

        return text, truncated, warnings
