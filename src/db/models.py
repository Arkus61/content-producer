"""SQLAlchemy ORM models — adapted for RF Federal Law 152-FZ compliance."""
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, Boolean, JSON, ForeignKey, func, Index, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from uuid import uuid4


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── 1. User (operator staff / admin)
# ──────────────────────────────────
# Minimal user table for the operator personnel who manage the system.
# NOT for end-experts — experts are data subjects under 152-FZ.

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="operator")  # operator, admin, viewer
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ── 2. Expert Card (PDn subject) ─────────────────────────

class ExpertCardModel(Base):
    __tablename__ = "expert_cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    # ── Identity ──
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str] = mapped_column(String(255), server_default="")
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    city: Mapped[str] = mapped_column(String(255), server_default="")
    profession: Mapped[str] = mapped_column(String(255), server_default="")

    # ── Content ──
    expertise: Mapped[list] = mapped_column(JSON, server_default="[]")
    uvp: Mapped[str] = mapped_column(Text, server_default="")
    tone_style: Mapped[str] = mapped_column(String(50), server_default="expert")
    tone_format_pref: Mapped[str] = mapped_column(String(50), server_default="paragraphs")
    tone_emoji_style: Mapped[str] = mapped_column(String(20), server_default="moderate")
    audience_demographics: Mapped[str] = mapped_column(Text, server_default="")
    audience_pains: Mapped[list] = mapped_column(JSON, server_default="[]")
    strategy_goals: Mapped[list] = mapped_column(JSON, server_default="[]")
    strategy_platforms: Mapped[list] = mapped_column(JSON, server_default="[]")
    strategy_frequency: Mapped[str] = mapped_column(String(50), server_default="")
    stories: Mapped[list] = mapped_column(JSON, server_default="[]")
    achievements: Mapped[list] = mapped_column(JSON, server_default="[]")

    # ── 152-FZ fields ──
    # full card dump for export / backup
    card_data: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    data_subject_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    data_subject_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    consent_granted: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_version: Mapped[str] = mapped_column(String(10), default="1.0")
    consent_granted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_anonymized: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # who created / owns the record (operator user linking)
    owner_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    interview_sessions = relationship("InterviewSessionModel", back_populates="expert", cascade="all, delete-orphan")
    transcriptions = relationship("TranscriptionModel", back_populates="expert", cascade="all, delete-orphan")
    content_items = relationship("ContentItemModel", back_populates="expert", cascade="all, delete-orphan")
    consent_log_entries = relationship("ConsentLog", back_populates="expert")
    export_log_entries = relationship("DataExportLog", back_populates="expert")
    deletion_log_entries = relationship("DataDeletionLog", back_populates="expert")

    __table_args__ = (
        Index("idx_expert_email", "data_subject_email"),
        Index("idx_expert_anon_retention", "is_anonymized", "retention_until"),
    )


# ── 3. Interview Session ─────────────────────────────────

class InterviewSessionModel(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    expert_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("expert_cards.id"), nullable=True)
    expert_name: Mapped[str] = mapped_column(String(255), server_default="")
    questions_asked: Mapped[int] = mapped_column(Integer, server_default="0")
    answers_collected: Mapped[int] = mapped_column(Integer, server_default="0")
    is_complete: Mapped[bool] = mapped_column(Boolean, server_default="false")
    responses: Mapped[dict] = mapped_column(JSON, server_default="{}")
    # link to operator user who created the session
    creator_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    retention_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    expert = relationship("ExpertCardModel", back_populates="interview_sessions")


# ── 4. Transcription ─────────────────────────────────────

class TranscriptionModel(Base):
    __tablename__ = "transcriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    expert_id = mapped_column(String(36), ForeignKey("expert_cards.id"), nullable=True)
    source_url = mapped_column(String(2048), nullable=True)
    source_type: Mapped[str] = mapped_column(String(20), server_default="file")
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(10), server_default="ru")
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    creator_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    retention_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    expert = relationship("ExpertCardModel", back_populates="transcriptions")


# ── 5. Content Item ──────────────────────────────────────

class ContentItemModel(Base):
    __tablename__ = "content_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    expert_id: Mapped[str] = mapped_column(String(36), ForeignKey("expert_cards.id"))
    content_type: Mapped[str] = mapped_column(String(20))
    platform: Mapped[str] = mapped_column(String(50), server_default="telegram")
    topic: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), server_default="draft")
    creator_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    published_at = mapped_column(DateTime, nullable=True)

    expert = relationship("ExpertCardModel", back_populates="content_items")


# ── 6. Consent Log (152-FZ Art. 9) ───────────────────────
# Records of data-subject consent for PDn processing.

class ConsentLog(Base):
    __tablename__ = "consent_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    expert_id: Mapped[str] = mapped_column(String(36), ForeignKey("expert_cards.id"), nullable=False)
    consent_type: Mapped[str] = mapped_column(String(50), nullable=False)  # interview, transcription, processing, marketing
    consent_version: Mapped[str] = mapped_column(String(10), default="1.0")
    is_granted: Mapped[bool] = mapped_column(Boolean, default=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    withdraw_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    expert = relationship("ExpertCardModel", back_populates="consent_log_entries")

    __table_args__ = (
        Index("idx_consent_expert_type", "expert_id", "consent_type"),
    )


# ── 7. Data Export Log (152-FZ Art. 14.1) ────────────────
# Log of data-subject requests for copies of their PDn.

class DataExportLog(Base):
    __tablename__ = "data_export_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    expert_id: Mapped[str] = mapped_column(String(36), ForeignKey("expert_cards.id"), nullable=False)
    export_format: Mapped[str] = mapped_column(String(20), default="json")  # json, pdf, xlsx
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    include_transcriptions: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, ready, expired, error
    requested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    expert = relationship("ExpertCardModel", back_populates="export_log_entries")


# ── 8. Data Deletion Log (152-FZ Art. 14) ────────────────
# Log of data-subject requests to stop processing / erase PDn.

class DataDeletionLog(Base):
    __tablename__ = "data_deletion_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    expert_id: Mapped[str] = mapped_column(String(36), ForeignKey("expert_cards.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="subject_request")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, processing, completed, failed
    deletion_scope: Mapped[str] = mapped_column(String(50), default="all")  # all, interview, transcriptions, partial
    requested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    executed_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    expert = relationship("ExpertCardModel", back_populates="deletion_log_entries")


# ── 9. Audit Log (152-FZ Art. 18.1) ──────────────────────
# Record of all operations with PDn for security monitoring.

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    record_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # create, read, update, delete, export, delete_request
    performed_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_audit_time", "created_at"),
        Index("idx_audit_user_action", "performed_by_user_id", "action"),
    )
