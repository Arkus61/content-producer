from __future__ import annotations

from datetime import datetime, timedelta
from ..expert_card.card import ExpertCard
from ..content_pipeline import PipelineDispatcher


async def generate_content_plan(
    card: ExpertCard,
    days: int = 7,
    api_key: str = "",
) -> list[dict]:
    """Generate a content plan using pipeline enrichment per item."""
    pipeline = PipelineDispatcher(api_key=api_key)

    topics = [
        ("educational", f"Как начать в {card.profession}"),
        ("personal", "Мой путь в экспертность"),
        ("promotional", "Кейс: как я помог клиенту"),
        ("engagement", "Какое ваше главное препятствие?"),
        ("educational", f"5 ошибок новичков в {card.profession}"),
    ]

    plan: list[dict] = []
    memory_notes: list[str] = []

    for i, (pillar, topic) in enumerate(topics[:days]):
        result = await pipeline.run(
            card=card,
            topic=topic,
            platform=card.strategy.platforms[0] if card.strategy.platforms else "telegram",
            content_type="plan_item",
            memory_notes=memory_notes,
        )
        plan.append({
            "day": (datetime.now() + timedelta(days=i)).isoformat(),
            "pillar": pillar,
            "topic": topic,
            "platform": card.strategy.platforms[0] if card.strategy.platforms else "telegram",
            "format": "post" if i % 2 == 0 else "video",
            "enriched_hook": result.get("score", {}).get("engagement_predicted", {}),
            "pipeline_logs": result.get("logs", []),
        })
        # Carry forward learnings
        sc = result.get("score", {})
        if sc.get("overall", 100) < 80:
            memory_notes.append(sc.get("rewrite_instruction", ""))

    return plan
