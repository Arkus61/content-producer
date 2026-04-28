import json
import openai
from ..expert_card.card import ExpertCard

async def generate_video_script(
    card: ExpertCard,
    topic: str,
    duration_minutes: int = 5,
    api_key: str = "",
) -> dict:
    client = openai.AsyncOpenAI(api_key=api_key)
    
    prompt = f"""Создай сценарий видео на {duration_minutes} минут.
ЭКСПЕРТ: {card.name}
СТИЛЬ: {card.tone.style}
ТЕМА: {topic}
Формат ответа JSON:
{{\"hook\": \"...\", \"intro\": \"...\", \"body\": [...], \"cta\": \"...\", \"b_roll_suggestions\": [...]}}"""
    
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)
