"""Social integration endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from ..config import settings
from ..db_client import db
from ..dependencies import get_current_user
from ..social_integrations import (
    PublishRequest, PublishResponse, SocialPublisher,
    TelegramPoster, InstagramPoster, PreviewRequest, PreviewResponse,
)

router = APIRouter(prefix="/api", tags=["social"])

_social_publisher: SocialPublisher | None = None


def _get_social_publisher() -> SocialPublisher:
    global _social_publisher
    if _social_publisher is None:
        telegram = None
        if settings.telegram_bot_token:
            telegram = TelegramPoster(settings.telegram_bot_token)
        instagram = None
        if settings.instagram_access_token and settings.instagram_account_id:
            instagram = InstagramPoster(settings.instagram_access_token, settings.instagram_account_id)
        _social_publisher = SocialPublisher(
            telegram_poster=telegram, instagram_poster=instagram,
            db_client=db if settings.supabase_url else None,
        )
    return _social_publisher


@router.post("/content/preview", response_model=PreviewResponse)
async def preview_post(req: PreviewRequest, user: dict = Depends(get_current_user)):
    publisher = _get_social_publisher()
    return await publisher.preview(PublishRequest(
        expert_id=user.get("id", ""), content=req.content,
        platform=req.platform, image_url=req.image_url, dry_run=True,
    ))


@router.post("/content/publish", response_model=PublishResponse)
async def publish_post(req: PublishRequest, user: dict = Depends(get_current_user)):
    if req.platform.value == "telegram" and not req.channel_id and settings.default_telegram_channel:
        req.channel_id = settings.default_telegram_channel
    publisher = _get_social_publisher()
    return await publisher.publish(req)


@router.get("/content/published")
async def list_published_posts(expert_id: str | None = None, platform: str | None = None,
                               skip: int = 0, limit: int = 20,
                               user: dict = Depends(get_current_user)):
    query = db.table("published_posts").select("*")
    if expert_id:
        query = query.eq("expert_id", expert_id)
    if platform:
        query = query.eq("platform", platform)
    result = await query.order("created_at", desc=True).range(skip, skip + limit - 1).execute()
    posts = result.data if hasattr(result, "data") else []
    return {"items": [{**p, "created_at": p.get("created_at")} for p in posts],
            "total": len(posts), "skip": skip, "limit": limit}
