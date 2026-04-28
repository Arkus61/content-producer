from datetime import datetime, timedelta
from ..expert_card.card import ExpertCard

def generate_content_plan(card: ExpertCard, days: int = 7) -> list[dict]:
    topics = [
        ("educational", f"Как начать в {card.profession}"),
        ("personal", "Мой путь в экспертность"),
        ("promotional", "Кейс: как я помог клиенту"),
        ("engagement", "Какое ваше главное препятствие?"),
        ("educational", f"5 ошибок новичков в {card.profession}"),
    ]
    
    plan = []
    for i, (pillar, topic) in enumerate(topics[:days]):
        plan.append({
            "day": (datetime.now() + timedelta(days=i)).isoformat(),
            "pillar": pillar,
            "topic": topic,
            "platform": card.strategy.platforms[0] if card.strategy.platforms else "telegram",
            "format": "post" if i % 2 == 0 else "video",
        })
    return plan
