"""Pure data models — no ORM. Used with Supabase Client.

Supabase tables:
  expert_cards, interview_sessions, transcriptions, content_items,
  consent_logs, data_export_logs, data_deletion_logs, audit_logs
"""
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field, asdict
from uuid import uuid4
import json


@dataclass
class ExpertCard:
    id: str
    name: str
    nickname: str = ""
    age: Optional[int] = None
    profession: str = ""
    city: str = ""
    expertise: str = "[]"
    uvp: str = ""
    consent_granted: bool = False
    consent_version: str = "1.0"
    consent_granted_at: Optional[str] = None
    is_anonymized: bool = False
    retention_until: Optional[str] = None
    owner_user_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    data_subject_email: Optional[str] = None
    data_subject_phone: Optional[str] = None
    card_data: Optional[dict] = None

    # Content fields
    tone_style: str = ""
    tone_format_pref: str = ""
    tone_emoji_style: str = ""
    audience_demographics: str = ""
    audience_pains: str = "[]"
    strategy_goals: str = "[]"
    strategy_platforms: str = "[]"
    strategy_frequency: str = ""
    stories: str = "[]"
    achievements: str = "[]"

    @staticmethod
    def from_supabase(row: dict):
        return ExpertCard(**row)

    def to_supabase(self) -> dict:
        d = asdict(self)
        # Remove None for clean upsert
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class InterviewSession:
    id: str
    expert_id: Optional[str] = None
    expert_name: str = ""
    responses: str = "{}"
    is_complete: bool = False
    creator_user_id: Optional[str] = None
    created_at: Optional[str] = None
    retention_until: Optional[str] = None

    @staticmethod
    def from_supabase(row: dict):
        return InterviewSession(**row)


@dataclass
class Transcription:
    id: str
    expert_id: Optional[str] = None
    source_url: Optional[str] = None
    text: str = ""
    language: str = "ru"
    status: str = "pending"
    creator_user_id: Optional[str] = None
    created_at: Optional[str] = None
    retention_until: Optional[str] = None

    @staticmethod
    def from_supabase(row: dict):
        return Transcription(**row)


@dataclass
class ContentItem:
    id: str
    expert_id: str
    content_type: str
    topic: str
    content: str = ""
    platform: str = "telegram"
    status: str = "draft"
    creator_user_id: Optional[str] = None
    created_at: Optional[str] = None
    published_at: Optional[str] = None

    @staticmethod
    def from_supabase(row: dict):
        return ContentItem(**row)


@dataclass
class ConsentLog:
    id: str
    expert_id: str
    consent_type: str
    is_granted: bool = True
    consent_version: str = "1.0"
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    granted_at: Optional[str] = None
    withdraw_at: Optional[str] = None

    @staticmethod
    def from_supabase(row: dict):
        return ConsentLog(**row)


@dataclass
class DataExportLog:
    id: str
    expert_id: str
    export_format: str = "json"
    include_transcriptions: bool = True
    status: str = "pending"
    file_path: Optional[str] = None
    requested_at: Optional[str] = None
    completed_at: Optional[str] = None
    expires_at: Optional[str] = None

    @staticmethod
    def from_supabase(row: dict):
        return DataExportLog(**row)


@dataclass
class DataDeletionLog:
    id: str
    expert_id: str
    reason: str = "subject_request"
    deletion_scope: str = "all"
    status: str = "pending"
    requested_at: Optional[str] = None
    completed_at: Optional[str] = None
    executed_by_user_id: Optional[str] = None

    @staticmethod
    def from_supabase(row: dict):
        return DataDeletionLog(**row)


@dataclass
class AuditLog:
    id: Optional[int] = None
    table_name: str = ""
    record_id: str = ""
    action: str = ""
    performed_by_user_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: str = "{}"
    created_at: Optional[str] = None

    @staticmethod
    def from_supabase(row: dict):
        return AuditLog(**row)


@dataclass
class User:
    id: Optional[str] = None
    supabase_uid: Optional[str] = None
    email: str = ""
    full_name: str = ""
    role: str = "operator"
    is_active: bool = True
    created_at: Optional[str] = None

    @staticmethod
    def from_supabase(row: dict):
        return User(**row)
