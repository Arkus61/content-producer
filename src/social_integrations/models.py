"""Pydantic models for social integration APIs."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class Platform(str, Enum):
    telegram = "telegram"
    instagram = "instagram"


class PublishRequest(BaseModel):
    """Request to publish generated content to a platform."""
    expert_id: str
    content: str = Field(description="Generated post text")
    platform: Platform = Field(default=Platform.telegram)
    channel_id: Optional[str] = Field(default=None, description="Telegram channel/@username or Instagram account")
    image_url: Optional[str] = Field(default=None, description="URL of image to attach")
    caption: Optional[str] = Field(default=None, description="Override caption (for Instagram)")
    hashtags: list[str] = Field(default_factory=list, description="Hashtags to append")
    schedule_at: Optional[datetime] = Field(default=None, description="Schedule for later (UTC)")
    dry_run: bool = Field(default=False, description="If True, only return preview without publishing")


class PublishResult(BaseModel):
    """Result of a single platform publish attempt."""
    platform: str
    success: bool
    message_id: Optional[str] = None
    post_url: Optional[str] = None
    error: Optional[str] = None
    published_at: Optional[datetime] = None


class PublishResponse(BaseModel):
    """Response after publish attempt."""
    task_id: str
    expert_id: str
    results: list[PublishResult]
    preview: Optional[dict] = None
    dry_run: bool = False


class PreviewRequest(BaseModel):
    """Request to generate a preview of how the post will look."""
    content: str
    platform: Platform = Field(default=Platform.telegram)
    image_url: Optional[str] = None
    max_length: int = Field(default=4096, description="Max chars for preview")


class PreviewResponse(BaseModel):
    """Preview of the post as it will appear on the platform."""
    platform: str
    rendered_text: str
    truncated: bool
    char_count: int
    line_count: int
    estimated_read_time_sec: int
    image_preview_url: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class PublishedPostRecord(BaseModel):
    """Record of a published post stored in DB."""
    id: str
    expert_id: str
    task_id: str
    platform: str
    content_preview: str
    message_id: Optional[str]
    post_url: Optional[str]
    status: str  # published, failed, scheduled, cancelled
    created_at: datetime
    published_at: Optional[datetime]
    error_log: Optional[str] = None
