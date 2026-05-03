"""Research Agent — enriches topic with audience hooks, insights, narrative angle."""
from __future__ import annotations

import json
from .base import BaseAgent
from .models import PipelineContext
from ..expert_card.card import ExpertCard


class ResearcherAgent(BaseAgent):
    """Enriches raw topic with expert-specific depth."""

    async def run(self, ctx: PipelineContext) -> None:
        assert ctx.expert_id, "expert_id required"
        card: ExpertCard = getattr(ctx, "_card", None)
        assert isinstance(card, ExpertCard), "ExpertCard must be attached to context as _card"

        safe_topic = self._topic_block(ctx.topic)
        user = (
            f"Expert: {card.name}\n"
            f"Profession: {card.profession}\n"
            f"Tone: {card.tone.style}, emoji_style={card.tone.emoji_style}\n"
            f"Audience core: {card.audience.core_segment}\n"
            f"Audience mass: {card.audience.mass_segment}\n"
            f"Pain points: {', '.join(card.audience.pain_points)}\n"
            f"Expertise: {', '.join(card.expertise_profile.unique_skills or [])}\n"
            f"Mission: {card.expertise_profile.mission}\n"
            f"Product: {card.product.name} – {card.product.description}\n"
            f"Topic: {safe_topic}\n"
        )
        if mem := self._memory_block(ctx):
            user += mem

        raw = await self._call(
            user=user,
            response_format="json_object",
            temperature=0.5,
        )
        try:
            ctx.enriched = json.loads(raw)
        except json.JSONDecodeError:
            ctx.enriched = {"raw": raw}
        ctx.audience_summary = ctx.enriched.get("audience_hook", "")
        ctx.log(f"researcher done: enriched keys={list(ctx.enriched.keys())}")

        await self.reflect(ctx, "Researcher analyzed topic and extracted audience hooks, insights, and narrative angle.")
