"""SQLAlchemy ORM models."""
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, Boolean, JSON, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from uuid import uuid4


class Base(DeclarativeBase):
    pass


def utcnow():
    return datetime.now(timezone.utc)


class ExpertCardModel(Base):
    __tablename__ = "expert_cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str] = mapped_column(String(255), server_default="")
    profession: Mapped[str] = mapped_column(String(255), server_default="")
    city: Mapped[str] = mapped_column(String(255), server_default="")
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
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    interview_sessions = relationship("InterviewSessionModel", back_populates="expert", cascade="all, delete-orphan")
    transcriptions = relationship("TranscriptionModel", back_populates="expert", cascade="all, delete-orphan")
    content_items = relationship("ContentItemModel", back_populates="expert", cascade="all, delete-orphan")


class InterviewSessionModel(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    expert_id: Mapped[str] = mapped_column(String(36), ForeignKey("expert_cards.id"), nullable=True)
    expert_name: Mapped[str] = mapped_column(String(255), server_default="")
    questions_asked: Mapped[int] = mapped_column(Integer, server_default="0")
    answers_collected: Mapped[int] = mapped_column(Integer, server_default="0")
    is_complete: Mapped[bool] = mapped_column(Boolean, server_default="false")
    responses: Mapped[dict] = mapped_column(JSON, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    expert = relationship("ExpertCardModel", back_populates="interview_sessions")


class TranscriptionModel(Base):
    __tablename__ = "transcriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    expert_id = mapped_column(String(36), ForeignKey("expert_cards.id"), nullable=True)
    source_url = mapped_column(String(2048), nullable=True)
    source_type: Mapped[str] = mapped_column(String(20), server_default="file")
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(10), server_default="ru")
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    expert = relationship("ExpertCardModel", back_populates="transcriptions")


class ContentItemModel(Base):
    __tablename__ = "content_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    expert_id: Mapped[str] = mapped_column(String(36), ForeignKey("expert_cards.id"))
    content_type: Mapped[str] = mapped_column(String(20))
    platform: Mapped[str] = mapped_column(String(50), server_default="telegram")
    topic: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), server_default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    published_at = mapped_column(DateTime, nullable=True)

    expert = relationship("ExpertCardModel", back_populates="content_items")
