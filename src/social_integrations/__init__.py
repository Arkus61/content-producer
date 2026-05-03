"""Social integrations module — Telegram + Instagram posting with preview generation."""
from .models import (
    PublishRequest,
    PublishResponse,
    PublishResult,
    PreviewRequest,
    PreviewResponse,
    PublishedPostRecord,
)
from .telegram_poster import TelegramPoster
from .instagram_poster import InstagramPoster
from .preview import PreviewGenerator
from .publisher import SocialPublisher

__all__ = [
    "PublishRequest",
    "PublishResponse",
    "PublishResult",
    "PreviewRequest",
    "PreviewResponse",
    "PublishedPostRecord",
    "TelegramPoster",
    "InstagramPoster",
    "PreviewGenerator",
    "SocialPublisher",
]