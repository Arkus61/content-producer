"""Writer Agent — produces draft content."""
from __future__ import annotations

from .base import BaseAgent
from .models import PipelineContext
from ..expert_card.card import ExpertCard


class WriterAgent(BaseAgent):
    """Generates first-pass draft content aligned with expert profile."""

    async def run(self, ctx: PipelineContext) -> None:
        card: ExpertCard = getattr(ctx, "_card", None)
        assert isinstance(card, ExpertCard), "ExpertCard must be attached to context"

        style = card.style
        style_lines = (
            f"VOCABULARY: {', '.join(style.vocabulary or [])}\n"
            f"SENTENCE_LENGTH: {style.sentence_length}\n"
            f"HUMOR_LEVEL: {style.humor_level}\n"
            f"EMOJI_USAGE: {style.emoji_usage}\n"
            f"STORY_STRUCTURE: {style.story_structure}\n"
            f"CTA_STYLE: {style.call_to_action_style}\n"
        ) if style.update_count > 0 else "(no style profile yet)"

        enriched = ctx.enriched or {}
        user = (
            f"Platform: {ctx.platform}\n"
            f"Format: {ctx.content_type}\n"
            f"Expert: {card.name} ({card.profession})\n"
            f"Tone: {card.tone.style}\n"
            f"Catchphrases: {', '.join(card.tone.catchphrases or [])}\n"
            f"Stop words: {', '.join(card.tone.stop_words or [])}\n"
            f"\nSTYLE PROFILE:\n{style_lines}\n"
            f"\nAUDIENCE HOOK:\n{enriched.get('audience_hook', '')}\n"
            f"\nKEY INSIGHTS:\n" + "\n".join(f"- {i}" for i in enriched.get("key_insights", [])) + "\n"
            f"\nNARRATIVE ANGLE:\n{enriched.get('narrative_angle', '')}\n"
            f"\nOBJECTIONS:\n" + "\n".join(f"- {o}" for o in enriched.get("objections", [])) + "\n"
            f"\nTOPIC:\n{self._topic_block(ctx.topic)}\n"
        )
        if ctx.memory_notes:
            user += "\nLEARNED PATTERNS:\n" + "\n".join(ctx.memory_notes) + "\n"
        if mem := self._memory_block(ctx):
            user += mem

        draft = await self._call(
            user=user,
            temperature=0.85,
        )
        ctx.draft = draft
        ctx.log(f"writer done: {len(draft)} chars")

        await self.reflect(ctx, f"Writer produced a {len(draft)}-char draft aligned with expert profile.")
