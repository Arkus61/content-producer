"""Social publisher — orchestrates posting + preview + DB tracking."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional, Protocol

from .models import (
    PublishRequest,
    PublishResponse,
    PublishResult,
    PreviewRequest,
    PreviewResponse,
    PublishedPostRecord,
    Platform,
)
from .preview import PreviewGenerator

logger = logging.getLogger("content-producer")


class _Poster(Protocol):
    async def publish(self, **kwargs) -> PublishResult:
        ...


class SocialPublisher:
    """Orchestrates publishing and preview across platforms."""

    def __init__(
        self,
        telegram_poster: Optional[_Poster] = None,
        instagram_poster: Optional[_Poster] = None,
        db_client: Optional[object] = None,
    ) -> None:
        self.telegram = telegram_poster
        self.instagram = instagram_poster
        self.db = db_client
        self.preview_gen = PreviewGenerator()

    async def preview(self, req: PublishRequest) -> PreviewResponse:
        """Generate preview without publishing."""
        preview_req = PreviewRequest(
            content=req.content,
            platform=req.platform,
            image_url=req.image_url,
        )
        return self.preview_gen.generate(preview_req)

    async def publish(self, req: PublishRequest) -> PublishResponse:
        """Publish to requested platform(s)."""
        task_id = str(uuid.uuid4())
        results: list[PublishResult] = []

        # If only preview requested
        if req.dry_run:
            preview = await self.preview(req)
            return PublishResponse(
                task_id=task_id,
                expert_id=req.expert_id,
                results=results,
                preview=preview.model_dump(),
                dry_run=True,
            )

        # Add hashtags if provided
        content = req.content
        if req.hashtags:
            hashtag_str = " ".join(f"#{h.strip('#')}" for h in req.hashtags if h.strip("#"))
            content = f"{content}\n\n{hashtag_str}"

        # Single platform publish
        if req.platform == Platform.telegram and self.telegram:
            result = await self.telegram.publish(
                chat_id=req.channel_id or "",
                text=content,
                image_url=req.image_url,
            )
            results.append(result)

        elif req.platform == Platform.instagram and self.instagram:
            if not req.image_url:
                results.append(
                    PublishResult(
                        platform="instagram",
                        success=False,
                        error="Instagram requires image_url",
                    )
                )
            else:
                result = await self.instagram.publish(
                    caption=content,
                    image_url=req.image_url,
                )
                results.append(result)

        else:
            results.append(
                PublishResult(
                    platform=req.platform.value,
                    success=False,
                    error=f"Platform {req.platform.value} not configured",
                )
            )

        # Save to DB if available
        if self.db:
            for r in results:
                await self._save_record(task_id, req, r)

        # Also return preview
        preview = await self.preview(req)

        return PublishResponse(
            task_id=task_id,
            expert_id=req.expert_id,
            results=results,
            preview=preview.model_dump(),
            dry_run=False,
        )

    async def _save_record(self, task_id: str, req: PublishRequest, result: PublishResult) -> None:
        """Persist publish result to Supabase DB."""
        try:
            record = PublishedPostRecord(
                id=str(uuid.uuid4()),
                expert_id=req.expert_id,
                task_id=task_id,
                platform=result.platform,
                content_preview=req.content[:500],
                message_id=result.message_id,
                post_url=result.post_url,
                status="published" if result.success else "failed",
                created_at=datetime.utcnow(),
                published_at=result.published_at,
                error_log=result.error,
            )
            await self.db.table("published_posts").insert(record.model_dump()).execute()
        except Exception as exc:
            logger.error("Failed to save published post record: %s", exc)
