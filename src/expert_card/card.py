from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ToneOfVoice(BaseModel):
    style: str = Field(description="friendly, expert, provocative, academic, humorous", default="expert")
    format_pref: str = Field(description="short/long sentences, paragraphs, lists", default="paragraphs")
    languages: list[str] = Field(default_factory=lambda: ["ru"])
    stop_words: list[str] = Field(default_factory=list)
    catchphrases: list[str] = Field(default_factory=list)
    emoji_style: str = Field(description="many/few/never", default="moderate")

class Audience(BaseModel):
    demographics: str = ""
    pain_points: list[str] = Field(default_factory=list)
    desires: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)

class ContentStrategy(BaseModel):
    goals: list[str] = Field(default_factory=list)
    frequency: str = ""
    formats: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    publishing_time: str = ""
    tone: str = ""

class ExpertCard(BaseModel):
    name: str
    nickname: str = ""
    age: Optional[int] = None
    city: str = ""
    profession: str = ""
    expertise: list[str] = Field(default_factory=list)
    uvp: str = Field(description="Unique value proposition", default="")
    tone: ToneOfVoice = Field(default_factory=ToneOfVoice)
    audience: Audience = Field(default_factory=Audience)
    strategy: ContentStrategy = Field(default_factory=ContentStrategy)
    stories: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_markdown(self) -> str:
        lines = [f"# Эксперт: {self.name}\n"]
        if self.nickname:
            lines.append(f"**Никнейм:** {self.nickname}")
        lines.append(f"**Профессия:** {self.profession}")
        lines.append(f"**Город:** {self.city}\n")
        lines.append(f"## Tone of Voice\n- Стиль: {self.tone.style}\n")
        lines.append(f"## Экспертиза\n" + "\n".join(f"- {e}" for e in self.expertise))
        lines.append(f"\n## Уникальное предложение\n{self.uvp}\n")
        if self.stories:
            lines.append("## Истории\n" + "\n".join(f"- {s}" for s in self.stories))
        return "\n".join(lines)
    
    @classmethod
    def from_markdown(cls, md: str) -> "ExpertCard":
        import re
        name = re.search(r"# Эксперт: (.+)", md)
        profession = re.search(r"\*\*Профессия:\*\* (.+)", md)
        return cls(
            name=name.group(1) if name else "Unknown",
            profession=profession.group(1) if profession else "",
        )
