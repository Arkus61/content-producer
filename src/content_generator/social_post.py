import openai
from ..expert_card.card import ExpertCard

async def generate_social_post(
    card: ExpertCard,
    topic: str,
    platform: str = "telegram",
    api_key: str = "",
) -> str:
    client = openai.AsyncOpenAI(api_key=api_key)
    
    prompt = f"""Создай пост для {platform} от имени эксперта.
ЭКСПЕРТ: {card.name}
ПРОФЕССИЯ: {card.profession}
СТИЛЬ: {card.tone.style}
ЭМОДЗИ: {card.tone.emoji_style}
ТЕМА: {topic}
Напиши пост в стиле эксперта, используя его tone of voice."""
    
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content

async def generate_post_series(
    card: ExpertCard,
    topics: list[str],
    platform: str = "telegram",
    api_key: str = "",
) -> list[str]:
    return [await generate_social_post(card, t, platform, api_key) for t in topics]
