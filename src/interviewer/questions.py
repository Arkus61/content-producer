from dataclasses import dataclass, field

@dataclass
class Question:
    id: str
    text: str
    category: str
    follow_ups: list[str] = field(default_factory=list)

QUESTION_BANK: list[Question] = [
    Question("intro_1", "Расскажите о себе: чем занимаетесь, какой у вас опыт?", "intro"),
    Question("intro_2", "Как вы пришли в свою нишу? Что вас мотивирует?", "intro",
             follow_ups=["Было ли это осознанное решение или вы пришли случайно?"]),
    Question("expertise_1", "В чём ваша главная экспертиза? Что вы знаете лучше большинства?", "expertise"),
    Question("expertise_2", "Какие 3-5 тем вы могли бы обсуждать часами?", "expertise"),
    Question("audience_1", "Кто ваша целевая аудитория? Кому вы хотите помогать?", "audience"),
    Question("audience_2", "Какие главные боли у вашей аудитории?", "audience"),
    Question("style_1", "Как бы вы описали свой стиль общения? (серьёзный, с юмором, провокационный)", "style"),
    Question("style_2", "Какие авторы или блогеры вам нравится читать/смотреть?", "style"),
    Question("goals_1", "Какие цели у вашего контента? (бренд, продажи, обучение)", "goals"),
    Question("goals_2", "Сколько времени в неделю вы готовы уделять контенту?", "goals"),
    Question("story_1", "Расскажите вашу самую яркую историю, связанную с вашей работой", "story"),
    Question("story_2", "Были ли моменты, когда вы всё хотели бросить? Что помогло?", "story"),
    Question("platform_1", "На каких платформах вы уже есть или хотите быть?", "platform"),
    Question("platform_2", "Какой формат контента вам ближе? (видео, текст, подкаст)", "platform"),
]

def get_questions_by_category(category: str) -> list[Question]:
    return [q for q in QUESTION_BANK if q.category == category]

def get_next_question(category: str, asked_ids: set[str]) -> Question | None:
    available = [q for q in QUESTION_BANK if q.category == category and q.id not in asked_ids]
    return available[0] if available else None
