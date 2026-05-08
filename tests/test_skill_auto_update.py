"""Tests for skill auto-update: suggest_skill_updates + apply_skill_update."""
import json
import pytest
from pathlib import Path
from src.content_pipeline.memory_agent import MemoryAgent
from src.content_pipeline.skill_loader import SkillRegistry, Skill


@pytest.fixture
def memory_agent(tmp_path):
    return MemoryAgent(data_dir=tmp_path)


@pytest.fixture
def populated_memory(memory_agent):
    """Memory with 12 runs across different topics/performances."""
    runs = [
        # High performers
        {"task_id": f"t{i}", "topic": "SaaS pricing strategy", "platform": "telegram",
         "final_score": 90, "iterations": 1}
        for i in range(1, 4)
    ] + [
        {"task_id": f"t{i}", "topic": "SaaS pricing mistakes", "platform": "telegram",
         "final_score": 30, "iterations": 3}
        for i in range(4, 7)
    ] + [
        # Mixed: some high, some low
        {"task_id": "t7", "topic": "growth hacking for B2B", "platform": "instagram",
         "final_score": 88, "iterations": 1},
        {"task_id": "t8", "topic": "growth hacking for B2B", "platform": "instagram",
         "final_score": 35, "iterations": 3},
        {"task_id": "t9", "topic": "building in public", "platform": "vk",
         "final_score": 92, "iterations": 1},
        {"task_id": "t10", "topic": "building in public", "platform": "vk",
         "final_score": 25, "iterations": 2},
        # More high performers on the same topic, cross-platform
        {"task_id": "t11", "topic": "SaaS pricing strategy", "platform": "vk",
         "final_score": 85, "iterations": 1},
        {"task_id": "t12", "topic": "SaaS pricing strategy", "platform": "vk",
         "final_score": 90, "iterations": 1},
        {"task_id": "t13", "topic": "SaaS pricing strategy", "platform": "vk",
         "final_score": 82, "iterations": 1},
    ]

    return memory_agent, runs


class TestSuggestSkillUpdates:
    """TDD: suggest_skill_updates() extracts patterns from memory."""

    @pytest.mark.asyncio
    async def test_returns_empty_for_insufficient_data(self, memory_agent):
        """Less than 5 runs → no suggestions."""
        for i in range(3):
            await memory_agent.ingest_run("expert-1", {
                "task_id": f"t{i}", "topic": "test", "platform": "telegram",
                "final_score": 50, "iterations": 1,
            })

        suggestions = await memory_agent.suggest_skill_updates("expert-1")
        assert suggestions == []

    @pytest.mark.asyncio
    async def test_finds_high_score_patterns(self, populated_memory):
        """>=5 runs with ≥3 high-scorers on same topic → suggests promoting that topic."""
        memory_agent, runs = populated_memory
        for r in runs:
            await memory_agent.ingest_run("expert-1", r)

        suggestions = await memory_agent.suggest_skill_updates("expert-1", min_runs=5, min_score=80)

        assert len(suggestions) > 0
        # Should find "SaaS pricing strategy" as strong topic (4 high scores)
        pricing_suggestions = [s for s in suggestions if "pricing" in s.get("topic", "").lower()]
        assert len(pricing_suggestions) > 0
        assert pricing_suggestions[0]["avg_score"] >= 80
        assert pricing_suggestions[0]["hit_count"] >= 3
        assert "suggested_action" in pricing_suggestions[0]

    @pytest.mark.asyncio
    async def test_finds_low_score_patterns(self, populated_memory):
        """Detects topics with consistently low scores."""
        memory_agent, runs = populated_memory
        for r in runs:
            await memory_agent.ingest_run("expert-1", r)

        suggestions = await memory_agent.suggest_skill_updates("expert-1", min_runs=5, max_score=50)

        assert len(suggestions) > 0
        # "SaaS pricing mistakes" — 3 runs all ≤30
        mistake_suggestions = [s for s in suggestions if "mistakes" in s.get("topic", "").lower()]
        assert len(mistake_suggestions) > 0
        assert mistake_suggestions[0]["avg_score"] <= 50
        assert "avoid" in mistake_suggestions[0]["suggested_action"].lower() or \
               "deprioritize" in mistake_suggestions[0]["suggested_action"].lower()

    @pytest.mark.asyncio
    async def test_finds_platform_patterns(self, populated_memory):
        """Detects platform-specific performance differences."""
        memory_agent, runs = populated_memory
        for r in runs:
            await memory_agent.ingest_run("expert-1", r)

        suggestions = await memory_agent.suggest_skill_updates("expert-1", min_runs=5)

        # Should detect that vk has mixed but telegram dominates for pricing
        assert any(s.get("platform") == "vk" for s in suggestions if s.get("platform"))


class TestApplySkillUpdate:
    """TDD: apply_skill_update() modifies SKILL.md in place."""

    @pytest.mark.asyncio
    async def test_adds_learned_pattern_and_evolution_entry(self, tmp_path):
        """apply_skill_update() adds pattern to learned_patterns and appends evolution_log."""
        # Setup a skill file
        agent_dir = tmp_path / "strategist" / "skills"
        agent_dir.mkdir(parents=True)
        (tmp_path / "strategist" / "agent.md").write_text(
            "---\nagent: strategist\nmodel: gpt-4o-mini\n---\n"
        )
        skill_file = agent_dir / "hook_generation.md"
        skill_content = """---
skill: hook_generation
version: 1
agent: strategist
category: creative
---

# Hook Generation

## Base Prompt
Generate hooks for {expert_name}.

## Learned Patterns
[]

## Evolution Log
[]"""
        skill_file.write_text(skill_content)

        registry = SkillRegistry(tmp_path)
        memory = MemoryAgent(data_dir=tmp_path / "memory")

        # Apply an update
        result = await memory.apply_skill_update(
            skill_registry=registry,
            agent_name="strategist",
            skill_name="hook_generation",
            update={
                "pattern": "money hooks (pricing, MRR)",
                "avg_score": 88.5,
                "hit_count": 5,
                "weight": "+15%",
                "source": "memory.suggest_skill_updates for expert-1",
            },
        )

        assert result["status"] == "applied"

        # Re-read the skill
        updated_skill = Skill(skill_file)
        assert len(updated_skill.learned_patterns) == 1
        assert updated_skill.learned_patterns[0]["pattern"] == "money hooks (pricing, MRR)"
        assert updated_skill.learned_patterns[0]["avg_score"] == 88.5
        assert updated_skill.learned_patterns[0]["weight"] == "+15%"

        assert len(updated_skill.evolution_log) == 1
        assert updated_skill.evolution_log[0]["change"] == "added pattern: money hooks (pricing, MRR)"
        assert updated_skill.version == 2  # auto-incremented

    @pytest.mark.asyncio
    async def test_appends_to_existing_patterns(self, tmp_path):
        """apply_skill_update() appends pattern when learned_patterns already has entries."""
        agent_dir = tmp_path / "creator" / "skills"
        agent_dir.mkdir(parents=True)
        (tmp_path / "creator" / "agent.md").write_text(
            "---\nagent: creator\nmodel: gpt-4o\n---\n"
        )
        skill_file = agent_dir / "draft_writing.md"
        skill_file.write_text("""---
skill: draft_writing
version: 2
agent: creator
category: writing
---

# Draft Writing

## Base Prompt
Write draft.

## Learned Patterns
- pattern: "contrarian angles"
  avg_score: 82.0
  hit_count: 3
  weight: "+10%"

## Evolution Log
- date: "2026-05-03"
  change: "added pattern: contrarian angles"
  source: "memory.insight #12"
""")

        registry = SkillRegistry(tmp_path)
        memory = MemoryAgent(data_dir=tmp_path / "memory")

        await memory.apply_skill_update(
            skill_registry=registry,
            agent_name="creator",
            skill_name="draft_writing",
            update={
                "pattern": "story-based openings",
                "avg_score": 86.0,
                "hit_count": 4,
                "weight": "+12%",
                "source": "memory.suggest_skill_updates",
            },
        )

        updated = Skill(skill_file)
        assert len(updated.learned_patterns) == 2
        assert updated.learned_patterns[1]["pattern"] == "story-based openings"
        assert updated.version == 3
        assert len(updated.evolution_log) == 2
