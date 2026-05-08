"""Phase 8: Self-Reflection + Skill Auto-Update — deep TDD tests.

Goes beyond existing suggest/apply unit tests:
- End-to-end: ingest 5+ runs → suggest → apply → verify SKILL.md on disk
- Dedup: same pattern twice → only one entry
- Dispatcher integration: mock dispatcher, verify it calls apply_skill_update
- Self-reflection gives actionable suggestions
"""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from src.content_pipeline.memory_agent import MemoryAgent
from src.content_pipeline.skill_loader import SkillRegistry, Skill

# ── Fixtures ───────────────────────────────────────────────

@pytest.fixture
def memory_agent(tmp_path):
    return MemoryAgent(data_dir=tmp_path)


@pytest.fixture
def skill_registry(tmp_path):
    """Minimal registry with trend_research + hook_generation skills."""
    agent_dir = tmp_path / "strategist" / "skills"
    agent_dir.mkdir(parents=True)
    (tmp_path / "strategist" / "agent.md").write_text(
        "---\nagent: strategist\nmodel: gpt-4o-mini\n---\n"
    )
    # trend_research
    (agent_dir / "trend_research.md").write_text("""---
skill: trend_research
version: 1
agent: strategist
category: analysis
---

## Base Prompt
Research trends for {expert_name} in {niche}.

## Learned Patterns
[]

## Evolution Log
[]""")
    # hook_generation (needed by suggest_skill_updates default target_skill)
    (agent_dir / "hook_generation.md").write_text("""---
skill: hook_generation
version: 1
agent: strategist
category: creative
---

## Base Prompt
Generate hooks for {expert_name}.

## Learned Patterns
[]

## Evolution Log
[]""")
    return SkillRegistry(tmp_path)


def _high_score_run(topic: str, task_id: str, score: float = 88.0) -> dict:
    return {
        "task_id": task_id,
        "topic": topic,
        "platform": "telegram",
        "content_type": "post",
        "content": f"Draft about {topic}...",
        "final_score": score,
        "score": {"overall": score},
        "iterations": 1,
    }


# ── End-to-End: Suggest → Apply → Verify Disk ─────────────────

@pytest.mark.asyncio
async def test_suggest_apply_pipeline_writes_skill_to_disk(memory_agent, skill_registry):
    """5+ high-score runs on same topic → suggest finds it → apply writes to SKILL.md."""
    topic = "remote team management"
    for i in range(7):
        await memory_agent.ingest_run("expert-1",
                                      _high_score_run(topic, f"run-{i}", score=85.0 + i))

    suggestions = await memory_agent.suggest_skill_updates("expert-1", min_runs=5)
    assert len(suggestions) > 0, "Should suggest promoting this topic"

    top = suggestions[0]
    target_skill = top.get("target_skill", "hook_generation")
    result = await memory_agent.apply_skill_update(
        skill_registry=skill_registry,
        agent_name=top.get("target_agent", "strategist"),
        skill_name=target_skill,
        update=top,
    )
    assert result["status"] == "applied"

    # Verify on disk
    skill_path = (Path(skill_registry.agents_dir) / "strategist" /
                  "skills" / f"{target_skill}.md")
    updated = Skill(skill_path)
    assert len(updated.learned_patterns) == 1
    assert "remote team management" in updated.learned_patterns[0]["pattern"]
    assert updated.learned_patterns[0]["avg_score"] > 80
    assert updated.version == 2
    assert len(updated.evolution_log) == 1


# ── Dedup ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_apply_skill_update_deduplicates_existing_pattern(memory_agent, skill_registry):
    """Applying the same pattern twice does not create a duplicate."""
    topic = "growth hacking frameworks"

    # Ingest 5 high-score runs
    for i, s in enumerate([90, 92, 88, 86, 91]):
        await memory_agent.ingest_run("expert-1",
                                      _high_score_run(topic, f"run-{i}", score=s))

    suggestions = await memory_agent.suggest_skill_updates("expert-1", min_runs=5, min_score=80)
    assert len(suggestions) > 0

    update = suggestions[0]
    target_skill = update.get("target_skill", "hook_generation")

    # First apply
    r1 = await memory_agent.apply_skill_update(
        skill_registry=skill_registry,
        agent_name=update.get("target_agent", "strategist"),
        skill_name=target_skill,
        update=update,
    )
    assert r1["status"] == "applied"

    # Second apply with same data
    r2 = await memory_agent.apply_skill_update(
        skill_registry=skill_registry,
        agent_name=update.get("target_agent", "strategist"),
        skill_name=target_skill,
        update={"pattern": update.get("topic", ""),
                "avg_score": update.get("avg_score", 0),
                "hit_count": update.get("hit_count", 0),
                "weight": update.get("weight", "0%"),
                "source": "memory.dedup-test"},
    )
    assert r2["status"] == "applied"

    # Verify no duplicates on disk
    skill_path = (Path(skill_registry.agents_dir) / "strategist" /
                  "skills" / f"{target_skill}.md")
    updated = Skill(skill_path)
    topic_matches = [p for p in updated.learned_patterns
                     if topic.lower() in p.get("pattern", "").lower()]
    assert len(topic_matches) == 1, f"Expected 1 entry for '{topic}', got {len(topic_matches)}"


# ── Dispatcher Integration ──────────────────────────────────

@pytest.mark.asyncio
async def test_dispatcher_applies_skill_updates_after_run(tmp_path):
    """PipelineDispatcher calls suggest_skill_updates + apply_skill_update after run."""
    import tempfile
    from src.content_pipeline.dispatcher import PipelineDispatcher
    from src.expert_card.card import ExpertCard

    # Setup agents on disk
    agents_dir = tmp_path / "agents"
    strategist_skills = agents_dir / "strategist" / "skills"
    strategist_skills.mkdir(parents=True)
    (agents_dir / "strategist" / "agent.md").write_text(
        "---\nagent: strategist\nmodel: gpt-4o-mini\nversion: 1\n---\n"
    )

    hook_skill = strategist_skills / "hook_generation.md"
    hook_skill.write_text("""---
skill: hook_generation
version: 1
agent: strategist
category: creative
---

## Base Prompt
Generate hooks for {expert_name} in {niche}.

## Learned Patterns
[]

## Evolution Log
[]""")

    for agent_name in ("creator", "editor"):
        ad = agents_dir / agent_name / "skills"
        ad.mkdir(parents=True)
        (agents_dir / agent_name / "agent.md").write_text(
            f"---\nagent: {agent_name}\nmodel: gpt-4o\nversion: 1\n---\n"
        )
        (ad / "minimal.md").write_text(f"""---
skill: minimal
version: 1
agent: {agent_name}
category: misc
---

## Base Prompt
Do nothing: {{expert_name}} / {{topic}} / {{text}}

## Learned Patterns
[]

## Evolution Log
[]""")

    card = ExpertCard(name="Test Expert", profession="SaaS consultant")
    memory_dir = tmp_path / "memory"

    # Pre-populate memory with 6 high-score runs
    prep_agent = MemoryAgent(data_dir=memory_dir)
    for i in range(6):
        await prep_agent.ingest_run("Test Expert", {
            "task_id": f"run-{i}",
            "topic": "SaaS pricing psychology",
            "platform": "telegram",
            "content_type": "post",
            "final_score": 87.0 + i,
            "iterations": 1,
        })

    # Mock LLM
    mock_openai = MagicMock()
    mock_openai.chat.completions.create = AsyncMock(return_value=MagicMock(
        choices=[MagicMock(message=MagicMock(
            content='{"audience_hook":"B2B", "hooks":["h1","h2","h3","h4","h5"]}'
        ))],
        usage=MagicMock(prompt_tokens=10, completion_tokens=20),
    ))

    with patch("openai.AsyncOpenAI", return_value=mock_openai):
        dispatcher = PipelineDispatcher(
            api_key="sk-test",
            agents_dir=agents_dir,
            memory_data_dir=memory_dir,
        )
        result = await dispatcher.run(card, "SaaS pricing psychology", "telegram")

    assert "content" in result
    assert "trace" in result

    # Verify SKILL.md updated
    updated = Skill(hook_skill)
    assert len(updated.learned_patterns) >= 1, \
        "Dispatcher should have called apply_skill_update"
    assert updated.version >= 2
    assert len(updated.evolution_log) >= 1


# ── Self-Reflection Gives Actionable Insights ──────────────

@pytest.mark.asyncio
async def test_self_reflection_returns_actionable_report(memory_agent):
    """self_reflection() after diverse runs returns health + gaps that a scheduler can act on."""
    for i in range(5):
        await memory_agent.ingest_run("expert-1", {
            "task_id": f"run-{i}",
            "topic": f"topic-{i}",
            "platform": "telegram",
            "final_score": 80.0 - i * 5,
            "iterations": 1,
        })

    r = await memory_agent.self_reflection("expert-1")

    assert r["total_runs"] == 5
    assert r["total_nodes"] >= 5  # at least topic nodes
    assert "health" in r
    assert "low_confidence_nodes" in r
    assert "missing_topic_links" in r
    assert "reflected_at" in r

    # After diverse topics, missing links should be > 0
    assert r["missing_topic_links"] > 0, \
        "Unrelated topics with no edges → missing_links detected as gap"


@pytest.mark.asyncio
async def test_skill_suggestions_respect_min_score_threshold(memory_agent):
    """suggest_skill_updates() with min_score=85 only returns topics averaging ≥85."""
    # 4 high + 1 low on same topic — avg = (90+91+88+92+30)/5 = 78.2 → below threshold
    for score in [90, 91, 88, 92, 30]:
        await memory_agent.ingest_run("expert-1",
                                      _high_score_run("SaaS pricing", f"r-{score}", score))

    suggestions = await memory_agent.suggest_skill_updates(
        "expert-1", min_runs=5, min_score=85
    )
    pricing_suggestions = [s for s in suggestions
                           if "pricing" in s.get("topic", "").lower()]
    assert pricing_suggestions == [], \
        "Topic averaging <85 should not be promoted"


@pytest.mark.asyncio
async def test_skill_suggestions_include_platform_breakdown(memory_agent):
    """Multi-platform runs: suggest includes platform: field when cross-platform."""
    for i in range(3):
        await memory_agent.ingest_run("expert-1", {
            "task_id": f"tg-{i}", "topic": "remote work",
            "platform": "telegram", "final_score": 90, "iterations": 1,
        })
        await memory_agent.ingest_run("expert-1", {
            "task_id": f"vk-{i}", "topic": "remote work",
            "platform": "vk", "final_score": 82, "iterations": 1,
        })

    suggestions = await memory_agent.suggest_skill_updates("expert-1", min_runs=5)
    assert len(suggestions) > 0

    assert any(s.get("platform") == "telegram" for s in suggestions
               if s.get("platform")), "Should detect telegram as high-performer"

    platform_suggestions = [s for s in suggestions
                            if s.get("target_skill") == "platform_optimization"]
    assert len(platform_suggestions) > 0, "Should suggest platform_optimization skill update"
