"""Editor Agent — scoring, critique, visual briefs (v2 skill-based).

Consolidates legacy CriticAgent and VisualBriefAgent into one agent
with two skill-based operations: score() and visual_brief().
"""
from __future__ import annotations

import json
import logging
from typing import Any

import openai

from .models import PipelineContext, ScoreResult
from .skill_loader import SkillRegistry

logger = logging.getLogger("content-producer.editor")


class EditorAgent:
    """v2 Editor: scores content and generates visual briefs.

    score() → fills ctx.score (drives the reflection loop)
    visual_brief() → fills ctx.visual_brief (runs after the loop)
    """

    def __init__(
        self,
        skill_registry: SkillRegistry,
        api_key: str = "",
        model: str = "gpt-4o",
        temperature: float = 0.3,
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

    # ── Scoring (in the loop) ──────────────────────────────────

    async def score(self, ctx: PipelineContext) -> None:
        """Score the draft and populate ctx.score with ScoreResult."""
        from ..expert_card.card import ExpertCard

        card: ExpertCard = getattr(ctx, "_card", None)
        assert isinstance(card, ExpertCard), "ExpertCard must be attached to context as _card"

        try:
            skill = self.skill_registry.get("editor", "multi_dimension_scoring")
        except KeyError:
            logger.warning("multi_dimension_scoring skill not found")
            ctx.score = ScoreResult(
                overall=50,
                critique="Scoring skill unavailable",
                rewrite_instruction="Improve content quality",
            )
            return

        variables = {
            "expert_name": card.name,
            "profession": getattr(card, "profession", "unknown"),
            "platform": ctx.platform,
            "content_type": ctx.content_type,
            "topic": ctx.topic,
            "text": ctx.draft,
        }

        try:
            prompt = skill.build_prompt(**variables)
        except (KeyError, ValueError) as exc:
            logger.warning("Failed to build scoring prompt: %s", exc)
            ctx.score = ScoreResult(overall=50, critique=f"Prompt build error: {exc}")
            return

        raw = await self._call_llm(prompt, response_format="json_object")

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            data = {
                "overall": 50,
                "style_match": 50,
                "engagement": 50,
                "readability": 50,
                "grammar": 100,
                "brand_consistency": 50,
                "call_to_action": 50,
                "audience_fit": 50,
                "critique": "Failed to parse editor JSON: " + raw[:200],
                "rewrite_instruction": "Improve clarity and style match.",
                "visual_brief": {},
                "engagement_predicted": {},
            }

        ctx.score = ScoreResult(**{k: v for k, v in data.items() if k in ScoreResult.model_fields})
        ctx.log(
            f"editor.score: overall={ctx.score.overall}, "
            f"engagement={ctx.score.engagement}"
        )

    # ── Visual Brief (after the loop) ──────────────────────────

    async def visual_brief(self, ctx: PipelineContext) -> None:
        """Generate visual brief for the final draft."""
        from ..expert_card.card import ExpertCard

        card: ExpertCard = getattr(ctx, "_card", None)
        assert isinstance(card, ExpertCard), "ExpertCard must be attached to context as _card"

        try:
            skill = self.skill_registry.get("editor", "visual_brief")
        except KeyError:
            logger.info("visual_brief skill not found — skipping")
            return

        variables = {
            "expert_name": card.name,
            "platform": ctx.platform,
            "content_type": ctx.content_type,
            "topic": ctx.topic,
            "product_name": getattr(card.product, "name", "") if getattr(card, "product", None) else "",
            "text": ctx.draft,
        }

        try:
            prompt = skill.build_prompt(**variables)
        except (KeyError, ValueError) as exc:
            logger.warning("Failed to build visual_brief prompt: %s", exc)
            return

        raw = await self._call_llm(prompt, response_format="json_object")

        try:
            brief = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            brief = {"raw": raw}

        ctx.visual_brief = brief or {}
        ctx.log(f"editor.visual_brief: keys={list(brief.keys())}")

    # ── LLM helpers ────────────────────────────────────────────

    async def _call_llm(
        self,
        prompt: str,
        response_format: str | None = None,
    ) -> str:
        """Call OpenAI with prompt, return raw text."""
        if not prompt.strip():
            return "{}"

        client = self._client_instance()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
        }
        if response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}

        resp = await client.chat.completions.create(**kwargs)

        choice = resp.choices[0]
        self.tokens_prompt += resp.usage.prompt_tokens if resp.usage else 0
        self.tokens_completion += resp.usage.completion_tokens if resp.usage else 0
        return choice.message.content or "{}"
