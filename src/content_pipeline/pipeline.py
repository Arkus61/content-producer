"""Pipeline orchestrator: runs agents, reflection loop, accumulates style.\nSupports per-agent markdown config via AgentRegistry."""
from __future__ import annotations

import asyncio
import json
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import PipelineContext, ScoreResult, PipelineLog
from .config_loader import AgentRegistry
from .researcher import ResearcherAgent
from .writer import WriterAgent
from .style_enforcer import StyleEnforcerAgent
from .engagement_optimizer import EngagementOptimizerAgent
from .critic import CriticAgent
from .visual_brief import VisualBriefAgent
from ..expert_card.card import ExpertCard, StyleProfile

_REWRITE_THRESHOLD = 80.0
_MAX_REFLECTION_ITERATIONS = 3


class ContentPipeline:
    """Orchestrates the full agent chain with self-reflection."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "gpt-4o",
        reflection_threshold: float = _REWRITE_THRESHOLD,
        max_iterations: int = _MAX_REFLECTION_ITERATIONS,
        agents_dir: str | Path | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.reflection_threshold = reflection_threshold
        self.max_iterations = max_iterations

        # Load per-agent configs from markdown files
        self.registry = AgentRegistry(agents_dir)

        self.researcher = ResearcherAgent(
            api_key=api_key, model=model, registry=self.registry
        )
        self.writer = WriterAgent(
            api_key=api_key, model=model, registry=self.registry
        )
        self.style_enforcer = StyleEnforcerAgent(
            api_key=api_key, model=model, registry=self.registry
        )
        self.engagement_optimizer = EngagementOptimizerAgent(
            api_key=api_key, model=model, registry=self.registry
        )
        self.critic = CriticAgent(
            api_key=api_key, model=model, registry=self.registry
        )
        self.visual_brief = VisualBriefAgent(
            api_key=api_key, model=model, registry=self.registry
        )

    async def run(
        self,
        card: ExpertCard,
        topic: str,
        platform: str = "telegram",
        content_type: str = "post",
        memory_notes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run the full pipeline and return final output with logs."""
        task_id = hashlib.sha256(
            f"{card.name}:{topic}:{platform}:{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:16]

        ctx = PipelineContext(
            expert_id=getattr(card, "id", card.name),
            topic=topic,
            platform=platform,
            content_type=content_type,
            memory_notes=memory_notes or [],
        )
        ctx._card = card  # type: ignore[attr-defined]

        start = time.monotonic()
        await self.researcher.run(ctx)

        iteration = 0
        while iteration <= self.max_iterations:
            iteration += 1
            ctx.iterations = iteration  # <-- agents see correct iteration number
            await self.writer.run(ctx)
            await self.style_enforcer.run(ctx)
            await self.engagement_optimizer.run(ctx)
            await self.critic.run(ctx)

            assert ctx.score is not None
            ctx.log(
                f"iteration {iteration}: overall={ctx.score.overall}, "
                f"engagement={ctx.score.engagement}, threshold={self.reflection_threshold}"
            )

            if ctx.score.overall >= self.reflection_threshold:
                ctx.log("score above threshold, stopping reflection loop")
                break

            if iteration >= self.max_iterations:
                ctx.log("max iterations reached, stopping")
                break

            ctx.memory_notes.append(
                f"Iteration {iteration} feedback (overall={ctx.score.overall}): "
                f"{ctx.score.rewrite_instruction}"
            )

        await self.visual_brief.run(ctx)
        self._update_style_profile(card, ctx)

        log = PipelineLog(
            task_id=task_id,
            expert_id=ctx.expert_id,
            topic=topic,
            platform=platform,
            content_type=content_type,
            final_score=ctx.score,
            iterations=iteration,
            max_iterations=self.max_iterations,
            tokens_prompt=(
                self.researcher.tokens_prompt + self.writer.tokens_prompt +
                self.style_enforcer.tokens_prompt + self.engagement_optimizer.tokens_prompt +
                self.critic.tokens_prompt + self.visual_brief.tokens_prompt
            ),
            tokens_completion=(
                self.researcher.tokens_completion + self.writer.tokens_completion +
                self.style_enforcer.tokens_completion + self.engagement_optimizer.tokens_completion +
                self.critic.tokens_completion + self.visual_brief.tokens_completion
            ),
            latency_sec=round(time.monotonic() - start, 2),
            model=self.model,
        )

        return {
            "content": ctx.draft,
            "visual_brief": ctx.visual_brief,
            "score": ctx.score.model_dump(),
            "iterations": iteration,
            "logs": ctx.logs,
            "task_id": task_id,
            "pipeline_log": log.model_dump(),
        }

    def _update_style_profile(self, card: ExpertCard, ctx: PipelineContext) -> None:
        """Learn from critic feedback and evolve style markers."""
        score = ctx.score
        assert score is not None
        style = card.style
        style.update_count += 1

        if score.style_match < 60:
            style.sentence_length = "short" if style.sentence_length == "long" else "mixed"
        if score.engagement is not None and score.engagement >= 85:
            style.humor_level = min(10, style.humor_level + 1)
        if score.engagement is not None and score.engagement <= 40:
            style.humor_level = max(0, style.humor_level - 1)
        if score.call_to_action is not None and score.call_to_action >= 85:
            style.call_to_action_style = "direct"
        elif score.call_to_action is not None and score.call_to_action <= 40:
            style.call_to_action_style = "soft"

        words = [w.lower() for w in ctx.draft.split() if len(w) > 3 and w.isalpha()]
        from collections import Counter
        freq = Counter(words)
        new_vocab = [w for w, c in freq.most_common(5) if c >= 2 and w not in style.vocabulary]
        style.vocabulary = (style.vocabulary + new_vocab)[:30]

        eng = score.engagement_predicted if score else {}
        if isinstance(eng, dict):
            likes = eng.get("likes_estimate", 0)
            if isinstance(likes, (int, float)) and likes > 500:
                style.emoji_usage = "moderate" if style.emoji_usage == "none" else "heavy"

        card.updated_at = datetime.now(timezone.utc)
        ctx.log(f"style_profile updated (count={style.update_count})")

    def _run(self, card: ExpertCard, topic: str, platform: str, content_type: str) -> dict[str, Any]:
        """Synchronous inner run: orchestrates the agents."""
        import asyncio
        return asyncio.run(self.run(card, topic, platform, content_type))
