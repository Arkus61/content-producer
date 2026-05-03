"""Critic / Judge Agent — scores content and drives the reflection loop."""
from __future__ import annotations

import json
from .base import BaseAgent
from .models import PipelineContext, ScoreResult
from ..expert_card.card import ExpertCard


class CriticAgent(BaseAgent):
    """Scores content against objective criteria."""

    async def run(self, ctx: PipelineContext) -> None:
        card: ExpertCard = getattr(ctx, "_card", None)
        assert isinstance(card, ExpertCard), "ExpertCard required"

        user = (
            f"Expert: {card.name} ({card.profession})\n"
            f"Platform: {ctx.platform}\n"
            f"Style: {card.tone.style}\n"
            f"Audience core: {card.audience.core_segment}\n"
            f"Audience mass: {card.audience.mass_segment}\n"
            f"Pain points: {', '.join(card.audience.pain_points or [])}\n"
            f"\n--- DRAFT TO SCORE ---\n{ctx.draft}\n--- END DRAFT ---\n"
        )
        if mem := self._memory_block(ctx):
            user += mem

        raw = await self._call(
            user=user,
            response_format="json_object",
            temperature=0.3,
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {
                "overall": 50,
                "style_match": 50,
                "engagement": 50,
                "engagement_predicted": {},
                "readability": 50,
                "grammar": 100,
                "brand_consistency": 50,
                "call_to_action": 50,
                "audience_fit": 50,
                "critique": "Failed to parse critic JSON: " + raw[:200],
                "rewrite_instruction": "Improve clarity and style match.",
                "visual_brief": {},
            }

        ctx.score = ScoreResult(**data)
        ctx.log(
            f"critic done: overall={ctx.score.overall}, "
            f"engagement={ctx.score.engagement}, rewrite={ctx.score.rewrite_instruction[:60] if ctx.score.rewrite_instruction else 'none'}"
        )

        await self.reflect(
            ctx,
            work_summary=f"Critic scored draft: overall={ctx.score.overall}, engagement={ctx.score.engagement}. "
            f"Rewrite instruction: {ctx.score.rewrite_instruction[:200]}",
        )
