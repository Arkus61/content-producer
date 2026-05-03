"""Telegram poster — publish posts via Telegram Bot API."""
from __future__ import annotations

import logging
import aiohttp
from typing import Optional

from .models import PublishResult

logger = logging.getLogger("content-producer")

_MAX_TEXT_LEN = 4096
_MAX_CAPTION_LEN = 1024


class TelegramPoster:
    """Posts content to Telegram channels/groups via Bot API."""

    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    async def publish(
        self,
        chat_id: str,
        text: str,
        image_url: Optional[str] = None,
        parse_mode: str = "HTML",
    ) -> PublishResult:
        """Publish text (optionally with image) to Telegram channel."""
        if not self.bot_token:
            return PublishResult(
                platform="telegram",
                success=False,
                error="Telegram bot token not configured",
            )

        # Validate / truncate
        if len(text) > _MAX_TEXT_LEN:
            text = text[:_MAX_TEXT_LEN - 3] + "..."
            truncated = True
        else:
            truncated = False

        try:
            if image_url:
                # send photo with caption
                caption = text
                if len(caption) > _MAX_CAPTION_LEN:
                    caption = caption[:_MAX_CAPTION_LEN - 3] + "..."
                    truncated = True

                payload = {
                    "chat_id": chat_id,
                    "caption": caption,
                    "photo": image_url,
                    "parse_mode": parse_mode,
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/sendPhoto",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        data = await resp.json()
            else:
                # send text only
                payload = {
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": False,
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/sendMessage",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        data = await resp.json()

            if data.get("ok"):
                result = data["result"]
                message_id = str(result.get("message_id"))
                chat = result.get("chat", {})
                chat_username = chat.get("username")
                chat_id_val = chat.get("id")
                if chat_username:
                    post_url = f"https://t.me/{chat_username}/{message_id}"
                else:
                    post_url = f"https://t.me/c/{str(chat_id_val).replace('-100', '')}/{message_id}"

                return PublishResult(
                    platform="telegram",
                    success=True,
                    message_id=message_id,
                    post_url=post_url,
                    published_at=result.get("date"),
                )
            else:
                error_desc = data.get("description", "Unknown Telegram error")
                logger.error("Telegram API error: %s", error_desc)
                return PublishResult(
                    platform="telegram",
                    success=False,
                    error=error_desc,
                )

        except aiohttp.ClientError as exc:
            logger.error("Telegram HTTP error: %s", exc)
            return PublishResult(
                platform="telegram",
                success=False,
                error=f"HTTP error: {exc}",
            )
        except Exception as exc:
            logger.error("Telegram unexpected error: %s", exc)
            return PublishResult(
                platform="telegram",
                success=False,
                error=f"Unexpected: {exc}",
            )
