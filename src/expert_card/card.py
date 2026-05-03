from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone


# ── Tone of Voice ──────────────────────────────────────

class ToneOfVoice(BaseModel):
    style: str = Field(description="friendly, expert, provocative, academic, humorous", default="expert")
    format_pref: str = Field(description="short/long sentences, paragraphs, lists", default="paragraphs")
    languages: list[str] = Field(default_factory=lambda: ["ru"])
    stop_words: list[str] = Field(default_factory=list)
    catchphrases: list[str] = Field(default_factory=list)
    emoji_style: str = Field(description="many/few/never", default="moderate")


# ── Audience ───────────────────────────────────────────

class Audience(BaseModel):
    demographics: str = ""
    pain_points: list[str] = Field(default_factory=list)
    desires: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    core_segment: str = Field(description="Ядро ЦА", default="")
    mass_segment: str = Field(description="Основная масса ЦА", default="")


# ── Content Strategy ───────────────────────────────────

class ContentStrategy(BaseModel):
    goals: list[str] = Field(default_factory=list)
    frequency: str = ""
    formats: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    publishing_time: str = ""
    tone: str = ""


# ── Personality Profile (from Block 1) ─────────────────

class PersonalityProfile(BaseModel):
    """Распаковка личности — кто этот человек за пределами профессии."""
    values: list[str] = Field(default_factory=list, description="Ключевые ценности и убеждения")
    traits: list[str] = Field(default_factory=list, description="Личностные качества")
    hobbies: list[str] = Field(default_factory=list, description="Увлечения и хобби")
    lifestyle: str = Field(default="", description="Образ жизни, привычки, распорядок")
    family_background: str = Field(default="", description="Семья, окружение, влияние")
    philosophy: str = Field(default="", description="Философия жизни, отношение к миру")
    inspirations: list[str] = Field(default_factory=list, description="Что вдохновляет")
    fun_facts: list[str] = Field(default_factory=list, description="Неожиданные факты")
    favorite_quote: str = Field(default="", description="Цитата, которая вдохновляет")
    childhood_dream: str = Field(default="", description="Кем мечтал стать в детстве")
    proud_of: str = Field(default="", description="Чем больше всего гордится")
    communication_style: str = Field(default="", description="Предпочтительный стиль общения")


# ── Style Profile (learned from pipeline reflection) ─────

class StyleProfile(BaseModel):
    """Style markers extracted from generated content and critic feedback."""
    vocabulary: list[str] = Field(default_factory=list, description="Words/phrases the expert uses frequently")
    sentence_length: str = Field(default="mixed", description="short, medium, long, mixed")
    humor_level: int = Field(default=5, ge=0, le=10, description="0-10 scale")
    emoji_usage: str = Field(default="moderate", description="none, minimal, moderate, heavy")
    story_structure: str = Field(default="hook-story-lesson", description="hook-story-lesson, question-answer, problem-solution")
    call_to_action_style: str = Field(default="soft", description="soft, direct, implied")
    update_count: int = Field(default=0, ge=0, description="How many times style was refined")


# ── Expertise Profile (from Block 2) ───────────────────

class ExpertiseProfile(BaseModel):
    """Распаковка экспертности — глубокая профессиональная экспертиза."""
    definition: str = Field(default="", description="Что такое экспертность по мнению эксперта")
    unique_skills: list[str] = Field(default_factory=list, description="Уникальные навыки и знания")
    journey: str = Field(default="", description="Путь в профессии, как пришёл к текущему уровню")
    growth_phases: list[str] = Field(default_factory=list, description="Фазы роста профессионализма")
    mistakes: list[str] = Field(default_factory=list, description="Ошибки и уроки из них")
    hacks: list[str] = Field(default_factory=list, description="Лайфхаки и неочевидные тонкости")
    risks: list[str] = Field(default_factory=list, description="Подводные камни и риски")
    market_trends: list[str] = Field(default_factory=list, description="Наблюдаемые тренды")
    competitors: list[str] = Field(default_factory=list, description="Конкуренты и лидеры рынка")
    competitive_advantage: str = Field(default="", description="Преимущество перед конкурентами")
    mission: str = Field(default="", description="Экспертная миссия")
    method: str = Field(default="", description="Собственная методика")
    achievements: list[str] = Field(default_factory=list, description="Артефакты: дипломы, сертификаты, кейсы")
    metrics: str = Field(default="", description="Уровень на языке цифр")
    ideal_day: str = Field(default="", description="Идеальный рабочий день")
    sources: list[str] = Field(default_factory=list, description="Рекомендуемые источники знаний")
    beliefs: list[str] = Field(default_factory=list, description="3 убеждения, которые не изменит")
    client_loves: list[str] = Field(default_factory=list, description="Что нравится клиентам")
    client_dislikes: list[str] = Field(default_factory=list, description="Что не нравится клиентам")


# ── Product Profile (from Block 3) ─────────────────────

class ProductProfile(BaseModel):
    """Распаковка продукта — что продаёт эксперт."""
    name: str = Field(default="", description="Название продукта/услуги")
    description: str = Field(default="", description="Описание продукта")
    problem: str = Field(default="", description="Какую проблему решает")
    differentiator: str = Field(default="", description="Чем отличается от аналогов")
    origin_story: str = Field(default="", description="Как возникла идея")
    production_process: list[str] = Field(default_factory=list, description="Этапы производства")
    quality_standards: list[str] = Field(default_factory=list, description="Стандарты качества")
    ideal_client: str = Field(default="", description="Описание идеального клиента")
    client_journey: list[str] = Field(default_factory=list, description="Путь клиента")
    common_objections: list[str] = Field(default_factory=list, description="Частые возражения")
    unique_advantages: list[str] = Field(default_factory=list, description="Непродуктовые преимущества")
    secrets: list[str] = Field(default_factory=list, description="Ноу-хау и секреты")
    guarantees: str = Field(default="", description="Гарантии и поддержка")
    pricing: str = Field(default="", description="Финансовые условия")
    loyalty_program: str = Field(default="", description="Программа лояльности")
    certifications: list[str] = Field(default_factory=list, description="Сертификаты, патенты, лицензии")
    failed_cases: list[str] = Field(default_factory=list, description="Неудачные кейсы и анализ")
    future_plans: list[str] = Field(default_factory=list, description="Планы развития продукта")


# ── Expert Card (master model) ─────────────────────────

class ExpertCard(BaseModel):
    """Полная карточка эксперта — результат распаковки 300 вопросов."""
    # Базовая информация
    name: str
    nickname: str = ""
    age: Optional[int] = None
    city: str = ""
    profession: str = ""

    # Профили из трёх блоков
    personality: PersonalityProfile = Field(default_factory=PersonalityProfile)
    expertise_profile: ExpertiseProfile = Field(default_factory=ExpertiseProfile)
    product: ProductProfile = Field(default_factory=ProductProfile)

    # Совместимость со старой версией
    expertise: list[str] = Field(default_factory=list)
    uvp: str = Field(description="Unique value proposition", default="")
    tone: ToneOfVoice = Field(default_factory=ToneOfVoice)
    audience: Audience = Field(default_factory=Audience)
    strategy: ContentStrategy = Field(default_factory=ContentStrategy)
    stories: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)

    # Style profile (learned from pipeline reflection)
    style: StyleProfile = Field(default_factory=StyleProfile)

    # Мета
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_markdown(self) -> str:
        lines = [f"# Эксперт: {self.name}", ""]
        if self.nickname:
            lines.append(f"**Никнейм:** {self.nickname}")
        lines.append(f"**Профессия:** {self.profession}")
        lines.append(f"**Город:** {self.city}")
        lines.append("")

        # Личность
        p = self.personality
        if p.values or p.traits:
            lines.append("## 🧑 Личность")
            if p.traits:
                lines.append(f"**Качества:** {', '.join(p.traits)}")
            if p.values:
                lines.append(f"**Ценности:** {', '.join(p.values)}")
            if p.lifestyle:
                lines.append(f"**Образ жизни:** {p.lifestyle}")
            if p.philosophy:
                lines.append(f"**Философия:** {p.philosophy}")
            if p.proud_of:
                lines.append(f"**Гордится:** {p.proud_of}")
            if p.hobbies:
                lines.append(f"**Хобби:** {', '.join(p.hobbies)}")
            lines.append("")

        # Экспертность
        ep = self.expertise_profile
        if ep.unique_skills or ep.mission:
            lines.append("## 💡 Экспертность")
            if ep.unique_skills:
                lines.append(f"**Навыки:** {', '.join(ep.unique_skills)}")
            if ep.mission:
                lines.append(f"**Миссия:** {ep.mission}")
            if ep.competitive_advantage:
                lines.append(f"**Преимущество:** {ep.competitive_advantage}")
            if ep.method:
                lines.append(f"**Методика:** {ep.method}")
            if ep.metrics:
                lines.append(f"**Цифры:** {ep.metrics}")
            if ep.beliefs:
                lines.append("**Убеждения:**")
                for b in ep.beliefs:
                    lines.append(f"- {b}")
            if ep.mistakes:
                lines.append("**Ошибки и уроки:**")
                for m in ep.mistakes:
                    lines.append(f"- {m}")
            if ep.hacks:
                lines.append("**Лайфхаки:**")
                for h in ep.hacks:
                    lines.append(f"- {h}")
            lines.append("")

        # Tone of Voice
        lines.append("## 🎤 Tone of Voice")
        lines.append(f"- Стиль: {self.tone.style}")
        if self.tone.catchphrases:
            lines.append(f"- Коронные фразы: {', '.join(self.tone.catchphrases)}")
        lines.append("")

        # Продукт
        pr = self.product
        if pr.name or pr.description:
            lines.append("## 📦 Продукт")
            if pr.name:
                lines.append(f"**Название:** {pr.name}")
            if pr.description:
                lines.append(f"**Описание:** {pr.description}")
            if pr.problem:
                lines.append(f"**Решает проблему:** {pr.problem}")
            if pr.differentiator:
                lines.append(f"**Отличие:** {pr.differentiator}")
            if pr.ideal_client:
                lines.append(f"**Идеальный клиент:** {pr.ideal_client}")
            if pr.secrets:
                lines.append("**Ноу-хау:**")
                for s in pr.secrets:
                    lines.append(f"- {s}")
            lines.append("")

        # Аудитория
        if self.audience.demographics:
            lines.append("## 👥 Аудитория")
            lines.append(self.audience.demographics)
            if self.audience.pain_points:
                lines.append("**Боли:**")
                for p in self.audience.pain_points:
                    lines.append(f"- {p}")
            lines.append("")

        # Совместимость: старое поле expertise
        if self.expertise and not ep.unique_skills:
            lines.append("## Экспертиза")
            for e in self.expertise:
                lines.append(f"- {e}")
            lines.append("")

        # Уникальное предложение
        if self.uvp:
            lines.append("## Уникальное предложение")
            lines.append(self.uvp)
            lines.append("")

        # Истории
        if self.stories:
            lines.append("## 📖 Истории")
            for s in self.stories:
                lines.append(f"- {s}")
            lines.append("")

        # Источники
        if ep.sources:
            lines.append("## 📚 Рекомендуемые источники")
            for s in ep.sources:
                lines.append(f"- {s}")

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
