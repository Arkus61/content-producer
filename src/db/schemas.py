"""Pydantic schemas for API request/response validation."""
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict
from typing import Optional
from datetime import datetime


# ── Auth Schemas ─────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    email_verified: bool
    phone_verified: bool
    last_login_at: Optional[datetime]
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=30)


# ── Expert Card ──────────────────────────────────────────

class ExpertCardBase(BaseModel):
    name: str
    nickname: str = ""
    age: Optional[int] = None
    profession: str = ""
    email: Optional[str] = None   # for consent / notifications
    phone: Optional[str] = None
    city: str = ""
    expertise: list[str] = []
    uvp: str = ""


class ExpertCardCreate(ExpertCardBase):
    consent_granted: bool = False  # must be True in production
    consent_version: str = "1.0"


class ExpertCardUpdate(BaseModel):
    name: Optional[str] = None
    nickname: Optional[str] = None
    age: Optional[int] = None
    profession: Optional[str] = None
    city: Optional[str] = None
    expertise: Optional[list[str]] = None
    uvp: Optional[str] = None
    # PDn access
    email: Optional[str] = None
    phone: Optional[str] = None


class ExpertCardResponse(ExpertCardBase):
    id: str
    consent_granted: bool
    consent_granted_at: Optional[datetime]
    is_anonymized: bool
    retention_until: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Consent ──────────────────────────────────────────────

class ConsentRequest(BaseModel):
    consent_type: str = "processing"   # interview, transcription, processing, marketing
    consent_version: str = "1.0"
    is_granted: bool = True


class ConsentResponse(BaseModel):
    id: str
    consent_type: str
    consent_version: str
    is_granted: bool
    granted_at: datetime


# ── Data Subject Rights (152-FZ) ─────────────────────────

class ExportRequest(BaseModel):
    export_format: str = "json"   # json, pdf
    include_transcriptions: bool = True


class ExportResponse(BaseModel):
    request_id: str
    status: str
    file_url: Optional[str] = None
    expires_at: Optional[datetime] = None


class DeletionRequest(BaseModel):
    reason: str = "subject_request"
    deletion_scope: str = "all"   # all, interview, transcriptions


class DeletionResponse(BaseModel):
    request_id: str
    status: str
    expected_completion: datetime


class AuditLogResponse(BaseModel):
    id: int
    action: str
    table_name: str
    record_id: str
    details: dict
    ip_address: Optional[str]
    created_at: datetime


# ── Transcription & Content ──────────────────────────────

class TranscriptionResponse(BaseModel):
    id: str
    expert_name: str = ""
    source: str = ""
    text_length: int = 0
    preview: str = ""
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContentItemResponse(BaseModel):
    id: str
    content_type: str
    platform: str
    topic: str
    content: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Interview ────────────────────────────────────────────

class InterviewStartRequest(BaseModel):
    expert_name: str


class InterviewAnswerRequest(BaseModel):
    answer: str


class GenerateContentRequest(BaseModel):
    content_type: str = Field(description="post or video")
    topic: str
    platform: str = "telegram"


class ContentPlanResponse(BaseModel):
    expert_id: str
    plan: list[dict]
    days: int = 7


class PaginationParams(BaseModel):
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    items: list
    total: int
    skip: int
    limit: int
