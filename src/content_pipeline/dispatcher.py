"""Pipeline Dispatcher — orchestrates A2A agent calls with reflection loop.

v2 architecture: 4 skill-based agents (Strategist → Creator → Editor + Memory).
No legacy agents remain — all migrated.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .a2a import A2AMessage, A2AResponse, A2ATrace
from .models import PipelineContext, ScoreResult, PipelineLog
from .memory_agent import MemoryAgent
from .skill_loader import SkillRegistry
from .strategist import StrategistAgent
from .creator import CreatorAgent
from .editor import EditorAgent
from ..expert_card.card import ExpertCard

_REWRITE_THRESHOLD = 80.0
_MAX_ITERATIONS = 3


class PipelineDispatcher:
    """Orchestrates content generation across 4 agents with A2A protocol."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "gpt-4o",
        reflection_threshold: float = _REWRITE_THRESHOLD,
        max_iterations: int = _MAX_ITERATIONS,
        agents_dir: str | Path | None = None,
        memory_data_dir: str | Path = "data/memory",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.reflection_threshold = reflection_threshold
        self.max_iterations = max_iterations

        if agents_dir is None:
            agents_dir = Path(__file__).with_name("agents")
        self.agents_dir = Path(agents_dir)

        # Skill registry
        self.skill_registry = SkillRegistry(self.agents_dir)

        # Memory agent (local JSON for now, pgvector later)
        self.memory = MemoryAgent(data_dir=memory_data_dir)

        # All v2 agents (loaded lazily)
        self._strategist: StrategistAgent | None = None
        self._creator: CreatorAgent | None = None
        self._editor: EditorAgent | None = None

    def _init_agents(self) -> None:
        """Lazy-load all v2 agents."""
        if self._strategist is not None:
            return

        self._strategist = StrategistAgent(
            skill_registry=self.skill_registry,
            api_key=self.api_key,
            model=self.model,
        )
        self._creator = CreatorAgent(
            skill_registry=self.skill_registry,
            api_key=self.api_key,
            model=self.model,
        )
        self._editor = EditorAgent(
            skill_registry=self.skill_registry,
            api_key=self.api_key,
            model=self.model,
        )

    async def run(
        self,
        card: ExpertCard,
        topic: str,
        platform: str = "telegram",
        content_type: str = "post",
        memory_notes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run the full pipeline with A2A tracing."""
        task_id = hashlib.sha256(
            f"{card.name}:{topic}:{platform}:{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:16]

        trace = A2ATrace()

        # Lazy-load all v2 agents
        self._init_agents()
        assert self._strategist is not None
        assert self._creator is not None
        assert self._editor is not None

        ctx = PipelineContext(
            expert_id=(getattr(card, "id", None) or card.name),
            topic=topic,
            platform=platform,
            content_type=content_type,
            memory_notes=memory_notes or [],
        )
        ctx._card = card  # type: ignore[attr-defined]

        start = time.monotonic()

        # ── Phase 1: Retrieve memory context ──
        mem_ctx = await self.memory.retrieve_context(ctx.expert_id, topic)
        if mem_ctx.get("top_performers"):
            ctx.memory_notes.append(
                "Top past performers: "
                + "; ".join(p["topic"] for p in mem_ctx["top_performers"][:3])
            )
        if mem_ctx.get("low_performers"):
            ctx.memory_notes.append(
                "Avoid patterns from: "
                + "; ".join(p["topic"] for p in mem_ctx["low_performers"][:3])
            )

        # ── Phase 2: Strategist v2 ──
        span_id = trace.start_span("strategist", "creator", "research")
        await self._strategist.run(ctx)
        trace.end_span(
            span_id,
            status="ok",
            skills_used=["trend_research", "hook_generation"],
            tokens_prompt=self._strategist.tokens_prompt,
            tokens_completion=self._strategist.tokens_completion,
        )

        # ── Phase 3: Creator + Editor loop ──
        iteration = 0
        while iteration <= self.max_iterations:
            iteration += 1
            ctx.iterations = iteration

            # Creator v2: draft → tone → platform (3 skills)
            span_w = trace.start_span("creator", "editor", f"create_iter{iteration}")
            await self._creator.run(ctx)
            trace.end_span(
                span_w,
                status="ok",
                skills_used=["draft_writing", "tone_matching", "platform_optimization"],
                tokens_prompt=self._creator.tokens_prompt,
                tokens_completion=self._creator.tokens_completion,
            )

            # Editor v2: score
            span_c = trace.start_span("editor", "creator", f"critique_iter{iteration}")
            await self._editor.score(ctx)
            trace.end_span(
                span_c,
                status="ok",
                skills_used=["multi_dimension_scoring"],
                tokens_prompt=self._editor.tokens_prompt,
                tokens_completion=self._editor.tokens_completion,
            )

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

        # ── Phase 4: Visual Brief ──
        span_v = trace.start_span("editor", None, "visual_brief")
        await self._editor.visual_brief(ctx)
        trace.end_span(span_v, status="ok", skills_used=["visual_brief"])

        # ── Phase 5: Style profile update ──
        self._update_style_profile(card, ctx)

        # ── Phase 6: Ingest to memory ──
        run_data = {
            "task_id": task_id,
            "topic": topic,
            "platform": platform,
            "content_type": content_type,
            "content": ctx.draft,
            "score": ctx.score.model_dump() if ctx.score else {},
            "iterations": iteration,
            "logs": ctx.logs,
            "trace": trace.to_dict(),
        }
        ingest_result = await self.memory.ingest_run(ctx.expert_id, run_data)

        # ── Phase 7: Housekeeping (lightweight, runs after every run) ──
        hk_report = await self.memory.run_housekeeping(ctx.expert_id)
        ctx.log(
            f"housekeeping: conflicts={len(hk_report.get('conflicts', []))}, "
            f"stale={len(hk_report.get('stale_edges', []))}, "
            f"gaps={len(hk_report.get('gaps', []))}, "
            f"pruned={hk_report.get('pruned_edges', 0)}, "
            f"health={hk_report.get('reflection', {}).get('health', 'unknown')}"
        )

        # ── Phase 8: Skill Auto-Update (from memory patterns) ──
        suggestions = await self.memory.suggest_skill_updates(ctx.expert_id)
        applied = 0
        for s in suggestions[:2]:  # apply at most 2 updates per run
            result = await self.memory.apply_skill_update(
                skill_registry=self.skill_registry,
                agent_name=s.get("target_agent", "strategist"),
                skill_name=s.get("target_skill", "hook_generation"),
                update=s,
            )
            if result.get("status") == "applied":
                applied += 1
                ctx.log(f"skill_auto_update: {result['skill']} → v{result['version']} ({result['pattern_added'][:60]})")

        if applied:
            ctx.log(f"skill_auto_update: {applied} skills updated from {len(suggestions)} suggestions")
        elif suggestions:
            ctx.log(f"skill_auto_update: {len(suggestions)} suggestions found (0 applied — need review)")

        # ── Build response ──
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
                self._strategist.tokens_prompt
                + self._creator.tokens_prompt
                + self._editor.tokens_prompt
            ),
            tokens_completion=(
                self._strategist.tokens_completion
                + self._creator.tokens_completion
                + self._editor.tokens_completion
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
            "trace": trace.to_dict(),
        }

    def _update_style_profile(self, card: ExpertCard, ctx: PipelineContext) -> None:
        score = ctx.score
        assert score is not None
        style = card.style
        style.update_count += 1

        if score.style_match < 60:
            style.sentence_length = (
                "short" if style.sentence_length == "long" else "mixed"
            )
        if score.engagement is not None and score.engagement >= 85:
            style.humor_level = min(10, style.humor_level + 1)
        if score.engagement is not None and score.engagement <= 40:
            style.humor_level = max(0, style.humor_level - 1)
        if score.call_to_action is not None and score.call_to_action >= 85:
            style.call_to_action_style = "direct"
        elif score.call_to_action is not None and score.call_to_action <= 40:
            style.call_to_action_style = "soft"

        words = [
            w.lower() for w in ctx.draft.split() if len(w) > 3 and w.isalpha()
        ]
        from collections import Counter

        freq = Counter(words)
        new_vocab = [
            w
            for w, c in freq.most_common(5)
            if c >= 2 and w not in style.vocabulary
        ]
        style.vocabulary = (style.vocabulary + new_vocab)[:30]

        eng = score.engagement_predicted if score else {}
        if isinstance(eng, dict):
            likes = eng.get("likes_estimate", 0)
            if isinstance(likes, (int, float)) and likes > 500:
                style.emoji_usage = (
                    "moderate" if style.emoji_usage == "none" else "heavy"
                )

        card.updated_at = datetime.now(timezone.utc)
        ctx.log(f"style_profile updated (count={style.update_count})")
