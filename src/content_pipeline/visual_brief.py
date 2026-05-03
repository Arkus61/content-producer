"""Visual Brief Agent — prepares visual support plan."""
from __future__ import annotations

import json
from .base import BaseAgent
from .models import PipelineContext
from ..expert_card.card import ExpertCard


class VisualBriefAgent(BaseAgent):
    """Generates visual support plan for the post."""

    async def run(self, ctx: PipelineContext) -> None:
        card: ExpertCard = getattr(ctx, "_card", None)
        assert isinstance(card, ExpertCard), "ExpertCard required"

        user = (
            f"Platform: {ctx.platform}\n"
            f"Content type: {ctx.content_type}\n"
            f"Expert: {card.name}\n"
            f"Product: {card.product.name}\n"
            f"\n--- FINAL DRAFT ---\n{ctx.draft}\n--- END ---\n"
        )
        raw = await self._call(
            user=user,
            response_format="json_object",
            temperature=0.5,
        )
        try:
            brief = json.loads(raw)
        except json.JSONDecodeError:
            brief = {"raw": raw}
        ctx.visual_brief = brief
        ctx.log(f"visual_brief done: keys={list(brief.keys())}")
