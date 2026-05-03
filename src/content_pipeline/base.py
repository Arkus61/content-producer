"""Base agent class with shared utilities — supports per-agent markdown config."""
from __future__ import annotations

import openai
import re
import json
from abc import ABC, abstractmethod
from typing import Any
from .models import PipelineContext, ScoreResult, AgentInsight
from .config_loader import AgentRegistry

_MAX_RETRY = 3


class BaseAgent(ABC):
    """Shared infrastructure for all pipeline agents."""

    def __init__(
        self,
        agent_id: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        api_key: str | None = None,
        registry: AgentRegistry | None = None,
    ) -> None:
        """Initialize with optional per-agent config from markdown file."""
        self.agent_id = agent_id or self.__class__.__name__.lower().replace("agent", "").strip() or "base"

        # Load from registry if available
        if registry is not None:
            self.cfg = registry.get(self.agent_id)
        else:
            self.cfg = None

        self.model = model or (self.cfg.model if self.cfg else "gpt-4o")
        self.temperature = temperature if temperature is not None else (self.cfg.temperature if self.cfg else 0.7)
        self.api_key = api_key or (self.cfg.api_key if self.cfg else "")
        self.tokens_prompt = 0
        self.tokens_completion = 0
        self._client: openai.AsyncOpenAI | None = None

    def _client_instance(self) -> openai.AsyncOpenAI:
        if self._client is None:
            self._client = openai.AsyncOpenAI(api_key=self.api_key)
        return self._client

    def _sanitize(self, text: str) -> str:
        text = text.strip()
        text = "".join(ch for ch in text if ch == "\n" or ord(ch) >= 32)
        return text

    def _topic_block(self, topic: str) -> str:
        safe = self._sanitize(topic)
        return f"```\n{safe}\n```"

    async def _call(
        self,
        system: str | None = None,
        user: str = "",
        response_format: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """Single LLM call with token tracking.\n\n        If `system` is None, loads from agent config file."""
        system_text = system or (self.cfg.system_prompt if self.cfg else self.DEFAULT_SYSTEM_PROMPT)
        temp = temperature if temperature is not None else self.temperature
        messages = [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user},
        ]
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": temp}
        if response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}

        client = self._client_instance()
        for attempt in range(1, _MAX_RETRY + 1):
            try:
                resp = await client.chat.completions.create(**kwargs)
                break
            except openai.APIError as exc:
                if attempt == _MAX_RETRY:
                    raise
                import asyncio
                await asyncio.sleep(attempt * 2)
        choice = resp.choices[0]
        self.tokens_prompt += resp.usage.prompt_tokens if resp.usage else 0
        self.tokens_completion += resp.usage.completion_tokens if resp.usage else 0
        return choice.message.content or ""

    @property
    def DEFAULT_SYSTEM_PROMPT(self) -> str:
        return "You are a helpful AI assistant."

    @abstractmethod
    async def run(self, ctx: PipelineContext) -> None:
        """Execute the agent and mutate context."""
        ...

    async def reflect(
        self,
        ctx: PipelineContext,
        work_summary: str = "",
        auto_generate: bool = True,
    ) -> AgentInsight:
        """Generate and store a structured reflection for other agents.

        If auto_generate=True, uses an LLM call to synthesize insights from
        work_summary. Otherwise uses the summary as key_observation."""
        if auto_generate:
            system = (
                "You are a reflective observer. Based on the work done in this "
                "iteration, produce a concise JSON object with these fields:\n"
                "- key_observation: what you noticed in this iteration\n"
                "- what_worked: tactics or choices that improved quality\n"
                "- what_failed: tactics or choices that hurt quality\n"
                "- suggestion_for_next: actionable advice for agents on the next iteration"
            )
            user_text = f"Work done: {work_summary}\n"
            if ctx.score:
                user_text += (
                    f"Scores: overall={ctx.score.overall} engagement={ctx.score.engagement} "
                    f"style_match={ctx.score.style_match} readability={ctx.score.readability}\n"
                )
            raw = await self._call(
                system=system,
                user=user_text,
                response_format="json_object",
                temperature=0.3,
            )
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {}
            insight = AgentInsight(
                agent_id=self.agent_id,
                iteration=ctx.iterations,
                key_observation=data.get("key_observation", "No observation"),
                what_worked=data.get("what_worked", ""),
                what_failed=data.get("what_failed", ""),
                suggestion_for_next=data.get("suggestion_for_next", ""),
            )
        else:
            insight = AgentInsight(
                agent_id=self.agent_id,
                iteration=ctx.iterations,
                key_observation=work_summary,
            )
        ctx.add_insight(insight)
        return insight

    def _memory_block(self, ctx: PipelineContext) -> str:
        """Get the shared-memory prompt block for injecting into LLM calls."""
        return ctx.memory_for_agent(self.agent_id, ctx.iterations)
