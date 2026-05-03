"""Engagement Optimizer Agent — maximizes platform-specific engagement."""
from __future__ import annotations

from .base import BaseAgent
from .models import PipelineContext
from ..expert_card.card import ExpertCard


class EngagementOptimizerAgent(BaseAgent):
    """Tactics-driven rewrite to maximize predicted engagement."""

    async def run(self, ctx: PipelineContext) -> None:
        card: ExpertCard = getattr(ctx, "_card", None)
        assert isinstance(card, ExpertCard), "ExpertCard required"

        platform_tips: dict[str, str] = {
            "telegram": "Telegram allows long-form. Use bold headings, bullet lists, and nested structure. Add line breaks for mobile readability. Keep paragraphs 1-3 lines.",
            "instagram": "Instagram favors short punchy sentences with heavy emoji and line breaks. Front-load emotion. CTA must be visual (e.g. 'double tap if...').",
            "vk": "VK audience likes community stories, polls, and informal tone. Longer posts acceptable but first 2 sentences crucial.",
        }

        user = (
            f"Platform: {ctx.platform}\n"
            f"Platform tips: {platform_tips.get(ctx.platform, 'Write natively for the platform.')}\n"
            f"Audience core: {card.audience.core_segment}\n"
            f"Audience pain: {', '.join(card.audience.pain_points or [])}\n"
            f"Product: {card.product.name}\n"
            f"\n--- DRAFT ---\n{ctx.draft}\n--- END DRAFT ---\n"
        )
        if mem := self._memory_block(ctx):
            user += mem

        optimized = await self._call(
            user=user,
            temperature=0.7,
        )
        ctx.draft = optimized
        ctx.log(f"engagement_optimizer done: {len(optimized)} chars")

        await self.reflect(ctx, f"EngagementOptimizer applied platform tactics ({len(optimized)} chars).")
