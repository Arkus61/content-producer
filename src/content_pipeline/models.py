from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Optional
from datetime import datetime, timezone


class AgentInsight(BaseModel):
    """A single agent's reflection for other agents to read."""
    agent_id: str
    iteration: int = 0
    key_observation: str = Field(default="", description="What the agent noticed in this iteration")
    what_worked: str = Field(default="", description="Tactics/choices that improved the output")
    what_failed: str = Field(default="", description="Tactics/choices that hurt the output")
    suggestion_for_next: str = Field(default="", description="Actionable advice for agents on next iteration")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_prompt_block(self) -> str:
        return (
            f"--- {self.agent_id} (iter #{self.iteration}) ---\n"
            f"Observed: {self.key_observation}\n"
            f"Worked: {self.what_worked}\n"
            f"Failed: {self.what_failed}\n"
            f"Suggestion: {self.suggestion_for_next}\n"
        )


class ScoreResult(BaseModel):
    """Critic agent output that drives the reflection loop."""
    overall: float = Field(default=0.0, ge=0, le=100)
    style_match: float = Field(default=0.0, ge=0, le=100)
    engagement: float = Field(default=0.0, ge=0, le=100)
    engagement_predicted: dict = Field(default_factory=dict)
    readability: float = Field(default=0.0, ge=0, le=100)
    grammar: float = Field(default=100.0, ge=0, le=100)
    brand_consistency: float = Field(default=0.0, ge=0, le=100)
    call_to_action: float = Field(default=0.0, ge=0, le=100)
    audience_fit: float = Field(default=0.0, ge=0, le=100)
    critique: str = Field(default="", description="Free-form improvement suggestions")
    rewrite_instruction: str = Field(default="", description="Instruction for Writer")
    visual_brief: dict = Field(default_factory=dict)


class PipelineLog(BaseModel):
    """Full trace of one pipeline run for debugging/evolution."""
    task_id: str = ""
    expert_id: str = ""
    topic: str = ""
    platform: str = "telegram"
    content_type: str = "post"
    final_score: ScoreResult = Field(default_factory=lambda: ScoreResult(overall=0.0))
    iterations: int = 0
    max_iterations: int = 3
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tokens_prompt: int = 0
    tokens_completion: int = 0
    latency_sec: float = 0.0
    model: str = "gpt-4o"
    version: str = "1"


class PipelineContext(BaseModel):
    """Mutable context shared across agents in a single pipeline run."""
    model_config = ConfigDict(extra='allow')

    expert_id: str = ""
    topic: str = ""
    platform: str = "telegram"
    content_type: str = "post"
    format_instructions: str = ""
    audience_summary: str = ""
    memory_notes: list[str] = Field(default_factory=list)
    shared_memory: list[AgentInsight] = Field(default_factory=list)
    draft: str = ""
    enriched: dict = Field(default_factory=dict)
    score: Optional[ScoreResult] = None
    visual_brief: dict = Field(default_factory=dict)
    final_output: Any = None
    logs: list[str] = Field(default_factory=list)
    iterations: int = 0

    def log(self, message: str) -> None:
        self.logs.append(message)

    def add_insight(self, insight: AgentInsight) -> None:
        """Store a structured insight from an agent for others to see."""
        self.shared_memory.append(insight)
        self.log(f"insight from {insight.agent_id} (iter #{insight.iteration})")

    def memory_prompt(self) -> str:
        """Format all shared insights into a prompt block for agents."""
        if not self.shared_memory:
            return ""
        blocks = [insight.to_prompt_block() for insight in self.shared_memory]
        return "\nSHARED MEMORY (insights from previous agents/iterations):\n" + "\n".join(blocks) + "\n"

    def memory_for_agent(self, agent_id: str, iteration: int) -> str:
        """Return only insights relevant to this agent and iteration."""
        if not self.shared_memory:
            return ""
        # Show all insights except this agent's own from same iteration
        filtered = [
            insight for insight in self.shared_memory
            if not (insight.agent_id == agent_id and insight.iteration == iteration)
        ]
        if not filtered:
            return ""
        blocks = [insight.to_prompt_block() for insight in filtered]
        return "\nSHARED MEMORY (insights from previous agents/iterations):\n" + "\n".join(blocks) + "\n"


class ReflectionMemory(BaseModel):
    """Accumulated knowledge about what worked for this expert."""
    expert_id: str
    style_evolution: list[dict] = Field(default_factory=list)
    top_performers: list[dict] = Field(default_factory=list)
    patterns_to_avoid: list[str] = Field(default_factory=list)
    low_score_feedback: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
