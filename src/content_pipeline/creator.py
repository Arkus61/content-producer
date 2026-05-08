"""Creator Agent — draft writing, tone matching, platform optimization (v2 skill-based).

Consolidates legacy WriterAgent, StyleEnforcerAgent, and EngagementOptimizerAgent
into one agent with 3 sequential skill calls: draft → style → optimize.
"""
from __future__ import annotations

import logging
from typing import Any

import openai

from .models import PipelineContext
from .skill_loader import SkillRegistry

logger = logging.getLogger("content-producer.creator")

# Skill execution order: draft first, then style, then platform
_SKILL_ORDER = ["draft_writing", "tone_matching", "platform_optimization"]


class CreatorAgent:
    """v2 Creator: writes draft, matches tone, optimizes for platform.

    Each skill is a separate LLM call. Output of one feeds into the next.
    """

    def __init__(
        self,
        skill_registry: SkillRegistry,
        api_key: str = "",
        model: str = "gpt-4o",
        temperature: float = 0.75,
    ) -> None:
        self.skill_registry = skill_registry
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.tokens_prompt = 0
        self.tokens_completion = 0
        self._client: openai.AsyncOpenAI | None = None

    def _client_instance(self) -> openai.AsyncOpenAI:
        if self._client is None:
            self._client = openai.AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def run(self, ctx: PipelineContext) -> None:
        """Execute creator pipeline: draft → tone match → platform optimize."""
        from ..expert_card.card import ExpertCard

        card: ExpertCard = getattr(ctx, "_card", None)
        assert isinstance(card, ExpertCard), "ExpertCard must be attached to context as _card"

        available = self.skill_registry.list_agent_skills("creator")
        if not available:
            logger.warning("No creator skills found — skipping writing")
            return

        # Start with existing draft or empty — each skill call overwrites it
        text = ctx.draft or ""

        for skill_name in _SKILL_ORDER:
            if skill_name not in available:
                continue  # skip missing skills gracefully

            text = await self._apply_skill(skill_name, card, ctx, text)
            ctx.draft = text
            ctx.log(f"creator.{skill_name}: {len(text)} chars")

    async def _apply_skill(
        self,
        skill_name: str,
        card: Any,
        ctx: PipelineContext,
        text: str,
    ) -> str:
        """Build prompt from skill, call LLM, return result text."""
        try:
            skill = self.skill_registry.get("creator", skill_name)
        except KeyError:
            logger.warning("Skill '%s' not found for creator", skill_name)
            return text

        # Build variables for skill prompt
        style = card.style
        enriched = ctx.enriched or {}

        variables: dict[str, str] = {
            "expert_name": card.name,
            "profession": getattr(card, "profession", "unknown"),
            "topic": ctx.topic,
            "platform": ctx.platform,
            "content_type": ctx.content_type,
            "tone": getattr(card.tone, "style", "neutral"),
            "sentence_length": getattr(style, "sentence_length", "mixed"),
            "humor_level": str(getattr(style, "humor_level", 5)),
            "emoji_usage": getattr(style, "emoji_usage", "none"),
            "story_structure": getattr(style, "story_structure", "hook-story-lesson"),
            "cta_style": getattr(style, "call_to_action_style", "soft"),
            "audience_hook": enriched.get("audience_hook", ""),
            "key_insights": "\n- ".join(enriched.get("key_insights", [])),
            "narrative_angle": enriched.get("narrative_angle", ""),
            "tone_style": getattr(card.tone, "style", "neutral"),
            "catchphrases": ", ".join(getattr(card.tone, "catchphrases", []) or []),
            "stop_words": ", ".join(getattr(card.tone, "stop_words", []) or []),
            "format_pref": getattr(card.tone, "format_pref", "long"),
            "text": text,
            "memory_notes": "\n".join(f"- {n}" for n in (ctx.memory_notes or [])),
        }

        try:
            prompt = skill.build_prompt(**variables)
        except (KeyError, ValueError) as exc:
            logger.warning("Failed to build prompt for skill %s: %s", skill_name, exc)
            return text

        if not prompt.strip():
            return text

        return await self._call_llm(prompt)

    async def _call_llm(self, prompt: str) -> str:
        """Call OpenAI with the skill prompt, return raw text."""
        if not prompt.strip():
            return ""

        client = self._client_instance()
        resp = await client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
        )

        choice = resp.choices[0]
        self.tokens_prompt += resp.usage.prompt_tokens if resp.usage else 0
        self.tokens_completion += resp.usage.completion_tokens if resp.usage else 0
        return choice.message.content or ""
