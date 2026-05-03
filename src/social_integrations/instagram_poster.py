"""Instagram poster — publish posts via Meta Graph API."""
from __future__ import annotations

import logging
import aiohttp
from typing import Optional
import asyncio

from .models import PublishResult

logger = logging.getLogger("content-producer")

_MAX_CAPTION_LEN = 2200  # Instagram caption limit
_MAX_HASHTAGS = 30


class InstagramPoster:
    """Post image+caption to Instagram via Meta Graph API."""

    def __init__(self, access_token: str, account_id: str) -> None:
        self.access_token = access_token
        self.account_id = account_id
        self.base_url = "https://graph.facebook.com/v19.0"

    async def publish(
        self,
        caption: str,
        image_url: str,
    ) -> PublishResult:
        """Publish image with caption to Instagram feed.

        Instagram requires image_url to be publicly accessible.
        """
        if not self.access_token or not self.account_id:
            return PublishResult(
                platform="instagram",
                success=False,
                error="Instagram access_token or account_id not configured",
            )

        if len(caption) > _MAX_CAPTION_LEN:
            caption = caption[:_MAX_CAPTION_LEN - 3] + "..."

        try:
            # Step 1: Create media container
            create_payload = {
                "caption": caption,
                "image_url": image_url,
                "access_token": self.access_token,
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/{self.account_id}/media",
                    data=create_payload,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    data = await resp.json()

            if "error" in data:
                error_msg = data["error"].get("message", "Unknown Meta error")
                logger.error("Instagram media creation failed: %s", error_msg)
                return PublishResult(
                    platform="instagram",
                    success=False,
                    error=f"Media creation: {error_msg}",
                )

            creation_id = data.get("id")
            if not creation_id:
                return PublishResult(
                    platform="instagram",
                    success=False,
                    error="No creation_id returned from Meta",
                )

            # Step 2: Wait for media to be ready (usually instant for images)
            await asyncio.sleep(2)

            # Step 3: Publish container
            publish_payload = {
                "creation_id": creation_id,
                "access_token": self.access_token,
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/{self.account_id}/media_publish",
                    data=publish_payload,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    publish_data = await resp.json()

            if "error" in publish_data:
                error_msg = publish_data["error"].get("message", "Unknown Meta error")
                logger.error("Instagram publish failed: %s", error_msg)
                return PublishResult(
                    platform="instagram",
                    success=False,
                    error=f"Publish: {error_msg}",
                )

            media_id = publish_data.get("id")
            post_url = f"https://instagram.com/p/{media_id}" if media_id else None

            return PublishResult(
                platform="instagram",
                success=True,
                message_id=media_id,
                post_url=post_url,
            )

        except aiohttp.ClientError as exc:
            logger.error("Instagram HTTP error: %s", exc)
            return PublishResult(
                platform="instagram",
                success=False,
                error=f"HTTP error: {exc}",
            )
        except Exception as exc:
            logger.error("Instagram unexpected error: %s", exc)
            return PublishResult(
                platform="instagram",
                success=False,
                error=f"Unexpected: {exc}",
            )
