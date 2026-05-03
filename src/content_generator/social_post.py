from __future__ import annotations

from ..expert_card.card import ExpertCard
from ..content_pipeline import ContentPipeline


async def generate_social_post(
    card: ExpertCard,
    topic: str,
    platform: str = "telegram",
    api_key: str = "",
) -> dict:
    """Generate a social post via the full agent chain."""
    pipeline = ContentPipeline(api_key=api_key)
    result = await pipeline.run(
        card=card,
        topic=topic,
        platform=platform,
        content_type="post",
    )
    return result


async def generate_post_series(
    card: ExpertCard,
    topics: list[str],
    platform: str = "telegram",
    api_key: str = "",
) -> list[dict]:
    """Generate a series of posts via the pipeline."""
    pipeline = ContentPipeline(api_key=api_key)
    results: list[dict] = []
    memory_notes: list[str] = []
    for topic in topics:
        result = await pipeline.run(
            card=card,
            topic=topic,
            platform=platform,
            content_type="post",
            memory_notes=memory_notes,
        )
        results.append(result)
        # Carrying forward low-score feedback for next topics
        score = result.get("score", {})
        if score.get("overall", 100) < 80:
            memory_notes.append(score.get("rewrite_instruction", ""))
    return results
