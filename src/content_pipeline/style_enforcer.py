"""Style Enforcer Agent — edits draft to sound like the expert."""
from __future__ import annotations

from .base import BaseAgent
from .models import PipelineContext
from ..expert_card.card import ExpertCard


class StyleEnforcerAgent(BaseAgent):
    """Fine-tunes draft to match expert's learned style profile."""

    async def run(self, ctx: PipelineContext) -> None:
        card: ExpertCard = getattr(ctx, "_card", None)
        assert isinstance(card, ExpertCard), "ExpertCard required"

        style = card.style
        user = (
            f"Platform: {ctx.platform}\n"
            f"Tone style: {card.tone.style}\n"
            f"Catchphrases: {', '.join(card.tone.catchphrases or [])}\n"
            f"Stop words: {', '.join(card.tone.stop_words or [])}\n"
            f"Vocabulary: {', '.join(style.vocabulary or [])}\n"
            f"Sentence length: {style.sentence_length}\n"
            f"Humor level: {style.humor_level}/10\n"
            f"Emoji usage: {style.emoji_usage}\n"
            f"Story structure: {style.story_structure}\n"
            f"CTA style: {style.call_to_action_style}\n"
            f"\n--- DRAFT ---\n{ctx.draft}\n--- END DRAFT ---\n"
        )
        if mem := self._memory_block(ctx):
            user += mem

        revised = await self._call(
            user=user,
            temperature=0.5,
        )
        ctx.draft = revised
        ctx.log(f"style_enforcer done: {len(revised)} chars")

        await self.reflect(ctx, f"StyleEnforcer revised draft to match expert style ({len(revised)} chars).")
