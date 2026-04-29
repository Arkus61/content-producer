"""Pydantic schemas for API request/response validation."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ExpertCardBase(BaseModel):
    name: str
    nickname: str = ""
    profession: str = ""
    city: str = ""
    expertise: list[str] = []
    uvp: str = ""


class ExpertCardCreate(ExpertCardBase):
    pass


class ExpertCardUpdate(BaseModel):
    name: Optional[str] = None
    nickname: Optional[str] = None
    profession: Optional[str] = None
    city: Optional[str] = None
    expertise: Optional[list[str]] = None
    uvp: Optional[str] = None


class ExpertCardResponse(ExpertCardBase):
    id: str
    stories: list[str] = []
    achievements: list[str] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TranscriptionResponse(BaseModel):
    id: str
    expert_name: str = ""
    source: str = ""
    text_length: int = 0
    preview: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class ContentItemResponse(BaseModel):
    id: str
    content_type: str
    platform: str
    topic: str
    content: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class PaginationParams(BaseModel):
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    items: list
    total: int
    skip: int
    limit: int
