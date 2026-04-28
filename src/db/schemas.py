from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ExpertCardCreate(BaseModel):
    name: str
    nickname: str = ""
    profession: str = ""
    expertise: list[str] = Field(default_factory=list)
    uvp: str = ""

class ExpertCardResponse(BaseModel):
    id: str
    name: str
    nickname: str
    profession: str
    expertise: list[str]
    uvp: str
    created_at: datetime
    updated_at: datetime

class InterviewStartRequest(BaseModel):
    expert_name: str

class InterviewAnswerRequest(BaseModel):
    answer: str

class GenerateContentRequest(BaseModel):
    topic: str
    content_type: str = "post"
    platform: str = "telegram"

class TranscriptionResponse(BaseModel):
    id: str
    expert_name: str
    source: str
    text: str
    created_at: datetime

class ContentPlanResponse(BaseModel):
    plan: list[dict]
