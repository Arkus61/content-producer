"""Strategist Agent — audience research, trend analysis, hook generation (v2 skill-based)."""
from __future__ import annotations

import json
import logging
from typing import Any

import openai

from .models import PipelineContext
from .skill_loader import SkillRegistry

logger = logging.getLogger("content-producer.strategist")

_DEFAULT_SKILLS = ["audience_analysis", "trend_research", "hook_generation"]


class StrategistAgent:
    """v2 Strategist: loads skills from registry, composes prompt, calls LLM.

    Replaces the legacy ResearcherAgent. Uses skill-based prompt construction
    with learned patterns injection. No longer extends BaseAgent — self-contained.
    """

    def __init__(
        self,
        skill_registry: SkillRegistry,
        api_key: str = "",
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
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
        """Execute strategist: load skills, call LLM, populate ctx.enriched."""
        from ..expert_card.card import ExpertCard

        card: ExpertCard = getattr(ctx, "_card", None)
        assert isinstance(card, ExpertCard), "ExpertCard must be attached to context as _card"

        # Collect available skills
        available = self.skill_registry.list_agent_skills("strategist")
        if not available:
            logger.warning("No strategist skills found — skipping research")
            return

        # Build composited prompt from skills
        prompt = self._build_composite_prompt(card, ctx.topic, ctx.platform, available)

        raw = await self._call_llm(prompt)

        try:
            ctx.enriched = json.loads(raw)
        except json.JSONDecodeError:
            ctx.enriched = {"raw": raw}

        ctx.audience_summary = ctx.enriched.get("audience_hook", "")
        ctx.log(f"strategist done: enriched keys={list(ctx.enriched.keys())}")

    def _build_composite_prompt(
        self,
        card: Any,
        topic: str,
        platform: str,
        skill_names: list[str],
    ) -> str:
        """Build a single composite prompt from all available strategist skills."""
        sections: list[str] = []

        for name in skill_names:
            try:
                skill = self.skill_registry.get("strategist", name)
            except KeyError:
                continue

            try:
                section = skill.build_prompt(
                    expert_name=card.name,
                    niche=getattr(card, "profession", "unknown"),
                    topic=topic,
                    platform=platform,
                    audience_hook=getattr(card.audience, "core_segment", ""),
                    pain_points=", ".join(getattr(card.audience, "pain_points", [])),
                    tone=getattr(card.tone, "style", "neutral"),
                )
                sections.append(section)
            except (KeyError, ValueError) as exc:
                logger.warning("Failed to build prompt for skill %s: %s", name, exc)

        if not sections:
            return ""

        # Combine with a system-level header
        system_header = (
            "You are a content strategist. Below are your task briefs. "
            "Execute each one and combine results into a single JSON output.\n\n"
        )
        output_spec = (
            "\n\n## Output Format\n"
            "Return a single JSON object combining results from all tasks:\n"
            '- "audience_hook": primary audience insight\n'
            '- "insights": list of key strategic insights\n'
            '- "hooks": list of 5-7 compelling hooks for the topic\n'
        )

        return system_header + "\n\n".join(sections) + output_spec

    async def _call_llm(self, prompt: str) -> str:
        """Call OpenAI with the composite prompt, return raw text."""
        if not prompt:
            return "{}"

        client = self._client_instance()
        resp = await client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            response_format={"type": "json_object"},
        )

        choice = resp.choices[0]
        self.tokens_prompt += resp.usage.prompt_tokens if resp.usage else 0
        self.tokens_completion += resp.usage.completion_tokens if resp.usage else 0
        return choice.message.content or "{}"
