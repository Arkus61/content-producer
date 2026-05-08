import tempfile
from pathlib import Path
from src.content_pipeline.skill_loader import Skill, SkillRegistry


SAMPLE_SKILL = """---
skill: hook_generation
version: 3
agent: strategist
category: creative
---

# Hook Generation

## Base Prompt
You generate hooks for {expert_name} in niche {niche}.

## Learned Patterns
- pattern: "money hooks"
  avg_er: 4.2
  used: 14
  weight: "+15%"
- pattern: "tech hooks"
  avg_er: 0.8
  used: 7
  weight: "-20%"

## Evolution Log
- date: "2026-05-10"
  change: "discovered money pattern"
  source: "memory.insight #47"
"""


def test_skill_parses_frontmatter():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(SAMPLE_SKILL)
        path = f.name
    try:
        skill = Skill(path)
        assert skill.name == "hook_generation"
        assert skill.version == 3
        assert skill.agent == "strategist"
        assert skill.category == "creative"
    finally:
        Path(path).unlink()


def test_skill_parses_base_prompt():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(SAMPLE_SKILL)
        path = f.name
    try:
        skill = Skill(path)
        assert "expert_name" in skill.base_prompt
        assert "niche" in skill.base_prompt
    finally:
        Path(path).unlink()


def test_skill_parses_learned_patterns():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(SAMPLE_SKILL)
        path = f.name
    try:
        skill = Skill(path)
        assert len(skill.learned_patterns) == 2
        assert skill.learned_patterns[0]["pattern"] == "money hooks"
        assert skill.learned_patterns[1]["weight"] == "-20%"
    finally:
        Path(path).unlink()


def test_skill_parses_evolution_log():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(SAMPLE_SKILL)
        path = f.name
    try:
        skill = Skill(path)
        assert len(skill.evolution_log) == 1
        assert skill.evolution_log[0]["source"] == "memory.insight #47"
    finally:
        Path(path).unlink()


def test_skill_build_prompt_injects_patterns():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(SAMPLE_SKILL)
        path = f.name
    try:
        skill = Skill(path)
        prompt = skill.build_prompt(expert_name="Test", niche="SaaS")
        assert "Test" in prompt
        assert "SaaS" in prompt
        assert "money hooks" in prompt
        assert "+15%" in prompt
        assert "tech hooks" in prompt
    finally:
        Path(path).unlink()


def test_skill_build_prompt_without_patterns():
    minimal = "---\nskill: simple\nversion: 1\n---\n\n## Base Prompt\nHello {name}\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(minimal)
        path = f.name
    try:
        skill = Skill(path)
        prompt = skill.build_prompt(name="World")
        assert prompt == "Hello World"
    finally:
        Path(path).unlink()


def test_skill_registry_discovers_skills(tmp_path):
    agent_dir = tmp_path / "strategist" / "skills"
    agent_dir.mkdir(parents=True)
    (agent_dir / "hook_generation.md").write_text(SAMPLE_SKILL)
    (agent_dir / "audience_analysis.md").write_text(
        "---\nskill: audience_analysis\nversion: 1\nagent: strategist\n---\n\n## Base Prompt\nAnalyze audience.\n"
    )

    registry = SkillRegistry(tmp_path)
    skills = registry.list_agent_skills("strategist")
    assert "hook_generation" in skills
    assert "audience_analysis" in skills

    skill = registry.get("strategist", "hook_generation")
    assert skill.version == 3


def test_skill_registry_handles_missing():
    registry = SkillRegistry("/nonexistent/path")
    assert registry.list_all() == {}


def test_skill_to_dict():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(SAMPLE_SKILL)
        path = f.name
    try:
        skill = Skill(path)
        d = skill.to_dict()
        assert d["name"] == "hook_generation"
        assert d["learned_patterns_count"] == 2
    finally:
        Path(path).unlink()
