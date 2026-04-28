from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime, timezone

class Base(DeclarativeBase): pass

class ExpertCardModel(Base):
    __tablename__ = "expert_cards"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    nickname = Column(String(255), default="")
    profession = Column(String(255), default="")
    expertise = Column(Text, default="[]")  # JSON
    uvp = Column(Text, default="")
    tone_of_voice = Column(Text, default="{}")  # JSON
    audience = Column(Text, default="{}")  # JSON
    strategy = Column(Text, default="{}")  # JSON
    stories = Column(Text, default="[]")  # JSON
    achievements = Column(Text, default="[]")  # JSON
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class InterviewSessionModel(Base):
    __tablename__ = "interview_sessions"
    
    id = Column(String(36), primary_key=True)
    expert_name = Column(String(255), nullable=False)
    expert_card_id = Column(String(36), ForeignKey("expert_cards.id"), nullable=True)
    responses = Column(Text, default="{}")  # JSON
    current_category = Column(String(50), default="intro")
    is_complete = Column(Boolean, default=False)
    progress_percent = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class TranscriptionModel(Base):
    __tablename__ = "transcriptions"
    
    id = Column(String(36), primary_key=True)
    expert_name = Column(String(255), nullable=False)
    expert_card_id = Column(String(36), ForeignKey("expert_cards.id"), nullable=True)
    source = Column(String(500), nullable=False)  # file path or URL
    source_type = Column(String(20), default="file")  # file, youtube
    text = Column(Text, nullable=False)
    language = Column(String(10), default="ru")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ContentItemModel(Base):
    __tablename__ = "content_items"
    
    id = Column(String(36), primary_key=True)
    expert_card_id = Column(String(36), ForeignKey("expert_cards.id"), nullable=False)
    content_type = Column(String(20), nullable=False)  # post, video, script
    topic = Column(String(500), nullable=False)
    platform = Column(String(50), default="telegram")
    body = Column(Text, default="")
    status = Column(String(20), default="draft")  # draft, approved, published
    scheduled_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
