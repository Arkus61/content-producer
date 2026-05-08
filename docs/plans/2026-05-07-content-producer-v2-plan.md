# Content Producer v2 — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Migrate from 6-agent chain to 4-agent skill-based architecture (Strategist, Creator, Editor, Memory) with A2A protocol, dispatcher orchestration, pgvector-backed knowledge graph, and self-learning skills.

**Architecture:** Skill-loader loads Markdown skills from `agents/{name}/skills/`. Dispatcher routes A2A JSON messages between agents. Memory agent maintains pgvector graph with housekeeping cycles. Old agents become skill sets under new agents.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, OpenAI API, PostgreSQL + pgvector (Supabase), pytest

---

## Phase 1: Skill Infrastructure

### Task 1: Create skill loader module

**Objective:** Parse SKILL.md files with YAML frontmatter, base_prompt, learned_patterns, evolution_log.

**Files:**
- Create: `src/content_pipeline/skill_loader.py`

**Step 1: Write the module**

```python
"""Skill loader: parses SKILL.md files with YAML frontmatter and learned patterns."""
from __future__ import annotations

import re
import yaml
from pathlib import Path
from typing import Any


def _extract_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = re.fullmatch(r"---\s*\n(.*?)\n---\s*\n?(.*)", text.strip(), re.DOTALL)
    if not match:
        return {}, text.strip()
    try:
        front = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        front = {}
    return front, match.group(2).strip()


def _extract_section(text: str, heading: str) -> str:
    """Extract content under ## Heading."""
    pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def _parse_learned_patterns(text: str) -> list[dict[str, Any]]:
    """Parse YAML list under ## Learned Patterns."""
    section = _extract_section(text, "Learned Patterns")
    if not section:
        return []
    try:
        return yaml.safe_load(section) or []
    except yaml.YAMLError:
        return []


def _parse_evolution_log(text: str) -> list[dict[str, Any]]:
    """Parse YAML list under ## Evolution Log."""
    section = _extract_section(text, "Evolution Log")
    if not section:
        return []
    try:
        return yaml.safe_load(section) or []
    except yaml.YAMLError:
        return []


class Skill:
    """Runtime representation of a loaded skill."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        raw = self.path.read_text(encoding="utf-8")
        self.frontmatter, self.body = _extract_frontmatter(raw)
        self.name: str = self.frontmatter.get("skill", self.path.stem)
        self.version: int = int(self.frontmatter.get("version", 1))
        self.agent: str = self.frontmatter.get("agent", "")
        self.category: str = self.frontmatter.get("category", "")
        self.base_prompt: str = _extract_section(self.body, "Base Prompt")
        self.learned_patterns: list[dict[str, Any]] = _parse_learned_patterns(self.body)
        self.evolution_log: list[dict[str, Any]] = _parse_evolution_log(self.body)

    def build_prompt(self, **variables) -> str:
        """Build final prompt: base_prompt + learned_patterns injection."""
        prompt = self.base_prompt.format(**variables)
        if self.learned_patterns:
            lines = ["\n\n## Learned Patterns (apply these weights):"]
            for p in self.learned_patterns:
                w = p.get("weight", "0%")
                lines.append(f"- {p.get('pattern', '')} (weight: {w})")
            prompt += "\n".join(lines)
        return prompt

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "agent": self.agent,
            "category": self.category,
            "base_prompt": self.base_prompt[:200] + "..." if len(self.base_prompt) > 200 else self.base_prompt,
            "learned_patterns_count": len(self.learned_patterns),
            "evolution_entries": len(self.evolution_log),
        }


class SkillRegistry:
    """Discovers and caches skills from agent skill directories."""

    def __init__(self, agents_dir: str | Path) -> None:
        self.agents_dir = Path(agents_dir)
        self._skills: dict[str, dict[str, Skill]] = {}  # agent_name -> skill_name -> Skill
        self._discover()

    def _discover(self) -> None:
        for agent_dir in sorted(self.agents_dir.iterdir()):
            if not agent_dir.is_dir():
                continue
            skills_dir = agent_dir / "skills"
            if not skills_dir.is_dir():
                continue
            agent_name = agent_dir.name
            self._skills[agent_name] = {}
            for skill_file in sorted(skills_dir.glob("*.md")):
                try:
                    skill = Skill(skill_file)
                    self._skills[agent_name][skill.name] = skill
                except Exception:
                    continue

    def get(self, agent_name: str, skill_name: str) -> Skill:
        if agent_name not in self._skills:
            raise KeyError(f"Agent '{agent_name}' not found in registry")
        if skill_name not in self._skills[agent_name]:
            raise KeyError(f"Skill '{skill_name}' not found for agent '{agent_name}'")
        return self._skills[agent_name][skill_name]

    def list_agent_skills(self, agent_name: str) -> list[str]:
        return list(self._skills.get(agent_name, {}).keys())

    def list_all(self) -> dict[str, list[str]]:
        return {agent: list(skills.keys()) for agent, skills in self._skills.items()}
```

### Task 2: Write tests for skill loader

**Objective:** Verify parsing of SKILL.md with all sections.

**Files:**
- Create: `tests/test_skill_loader.py`

```python
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
    # Setup directory structure
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
```

**Step 2: Run tests**

```bash
cd /root/content-producer && python -m pytest tests/test_skill_loader.py -v
```

Expected: all 9 tests pass.

### Task 3: Create skill directories and sample skills

**Objective:** Create directory structure and migrate existing prompts into SKILL.md format.

**Files:**
- Create: `src/content_pipeline/agents/strategist/agent.md`
- Create: `src/content_pipeline/agents/strategist/skills/audience_analysis.md`
- Create: `src/content_pipeline/agents/strategist/skills/trend_research.md`
- Create: `src/content_pipeline/agents/strategist/skills/hook_generation.md`
- Create: `src/content_pipeline/agents/strategist/skills/content_planning.md`
- Create: `src/content_pipeline/agents/creator/agent.md`
- Create: `src/content_pipeline/agents/creator/skills/draft_writing.md`
- Create: `src/content_pipeline/agents/creator/skills/tone_matching.md`
- Create: `src/content_pipeline/agents/creator/skills/story_structures.md`
- Create: `src/content_pipeline/agents/creator/skills/platform_optimization.md`
- Create: `src/content_pipeline/agents/editor/agent.md`
- Create: `src/content_pipeline/agents/editor/skills/multi_dimension_scoring.md`
- Create: `src/content_pipeline/agents/editor/skills/style_check.md`
- Create: `src/content_pipeline/agents/editor/skills/brand_alignment.md`
- Create: `src/content_pipeline/agents/editor/skills/visual_brief.md`
- Create: `src/content_pipeline/agents/editor/skills/final_review.md`
- Create: `src/content_pipeline/agents/memory/agent.md`
- Create: `src/content_pipeline/agents/memory/skills/ingest_run.md`
- Create: `src/content_pipeline/agents/memory/skills/retrieve_context.md`
- Create: `src/content_pipeline/agents/memory/skills/extract_insights.md`
- Create: `src/content_pipeline/agents/memory/skills/connect_facts.md`

**Step 1: Create strategist/agent.md**

```yaml
---
agent: strategist
model: gpt-4o-mini
temperature: 0.7
max_tokens: 2048
version: 1
description: "Анализ аудитории, трендов и генерация стратегии контента"
---
```

**Step 2: Create strategist/skills/audience_analysis.md**

```markdown
---
skill: audience_analysis
version: 1
agent: strategist
category: analysis
---

# Audience Analysis

## Base Prompt
You are a research analyst. Given expert {expert_name} in {niche}, analyze their target audience.

Output JSON:
- core_segment: who is the primary audience
- mass_segment: secondary/wider audience
- pain_points: list of top 5 pains
- triggers: what makes them act (fear, greed, status)
- objections: what stops them from buying
- where_they_hang_out: platforms and communities

## Learned Patterns
[]

## Evolution Log
[]
```

**Step 3: Create remaining skill files** (similar format for all 20 files).

Run `python -m py_compile` after each creation. Commit after each agent's skills.

---

## Phase 2: Memory Agent

### Task 4: Create memory schema migration

**Objective:** SQL migration for pgvector tables.

**Files:**
- Create: `supabase/migrations/20260507_add_memory_graph.sql`

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memory_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expert_id TEXT NOT NULL,
    agent_id TEXT NOT NULL DEFAULT 'memory',
    node_type TEXT NOT NULL,
    label TEXT NOT NULL,
    embedding VECTOR(1536),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_confirmed_at TIMESTAMPTZ DEFAULT now(),
    evidence_count INT DEFAULT 1,
    confidence FLOAT DEFAULT 0.5,
    is_archived BOOLEAN DEFAULT false,
    archived_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS memory_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expert_id TEXT NOT NULL,
    from_node_id UUID REFERENCES memory_nodes(id) ON DELETE CASCADE,
    to_node_id UUID REFERENCES memory_nodes(id) ON DELETE CASCADE,
    relation TEXT NOT NULL,
    weight FLOAT DEFAULT 0.5,
    evidence_count INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_confirmed_at TIMESTAMPTZ DEFAULT now(),
    is_tombstone BOOLEAN DEFAULT false,
    tombstoned_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expert_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'telegram',
    content_type TEXT NOT NULL DEFAULT 'post',
    final_score FLOAT,
    iterations INT DEFAULT 1,
    tokens_prompt INT DEFAULT 0,
    tokens_completion INT DEFAULT 0,
    latency_ms FLOAT DEFAULT 0.0,
    trace JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_spans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    trace_id TEXT,
    span_id TEXT,
    parent_span_id TEXT,
    from_agent TEXT NOT NULL,
    to_agent TEXT,
    task_type TEXT NOT NULL,
    status TEXT DEFAULT 'started',
    skills_used JSONB DEFAULT '[]'::jsonb,
    tokens_prompt INT DEFAULT 0,
    tokens_completion INT DEFAULT 0,
    latency_ms FLOAT DEFAULT 0.0,
    error TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_memory_nodes_expert ON memory_nodes(expert_id);
CREATE INDEX IF NOT EXISTS idx_memory_nodes_type ON memory_nodes(expert_id, node_type);
CREATE INDEX IF NOT EXISTS idx_memory_edges_expert ON memory_edges(expert_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_expert ON pipeline_runs(expert_id);
```

### Task 5: Create MemoryAgent class

**Objective:** Core Memory agent with pgvector operations.

**Files:**
- Create: `src/content_pipeline/memory_agent.py`

```python
"""Memory Agent — knowledge graph with pgvector + JSON cache."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger("content-producer.memory")


class MemoryAgent:
    """Manages expert knowledge graph: ingest, retrieve, housekeeping."""

    def __init__(self, db_client=None, data_dir: str | Path = "data/memory") -> None:
        self.db = db_client  # Supabase DB client or None for local-only
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # ── Ingest ──────────────────────────────────────────────

    async def ingest_run(self, expert_id: str, run_data: dict[str, Any]) -> str:
        """Save a completed pipeline run to local JSON + DB."""
        run_id = str(uuid4())
        run_data["id"] = run_id
        run_data["expert_id"] = expert_id
        run_data["ingested_at"] = datetime.now(timezone.utc).isoformat()

        # Local JSON cache
        expert_file = self.data_dir / f"{expert_id}.jsonl"
        with open(expert_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(run_data, ensure_ascii=False) + "\n")

        # TODO: DB insert when Supabase available
        if self.db:
            try:
                await self.db.memory_run_insert(run_data)
            except Exception:
                logger.warning("Failed to insert run to DB", exc_info=True)

        return run_id

    # ── Retrieve ────────────────────────────────────────────

    async def retrieve_context(
        self, expert_id: str, topic: str = "", limit: int = 5
    ) -> dict[str, Any]:
        """Return relevant context for the given expert and topic."""
        expert_file = self.data_dir / f"{expert_id}.jsonl"
        runs = []
        if expert_file.exists():
            with open(expert_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        runs.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        # Filter by topic relevance (simple keyword match for now, pgvector later)
        if topic:
            topic_lower = topic.lower()
            runs = [r for r in runs if topic_lower in json.dumps(r).lower()]

        recent = sorted(runs, key=lambda r: r.get("ingested_at", ""), reverse=True)[:limit]

        # Extract patterns
        all_insights = []
        high_scores = []
        low_scores = []
        for r in recent:
            score = r.get("final_score") or (r.get("score", {}) if isinstance(r.get("score"), dict) else {}).get("overall")
            if isinstance(score, dict):
                score = score.get("overall")
            if score and isinstance(score, (int, float)):
                if score >= 80:
                    high_scores.append({"topic": r.get("topic"), "score": score, "draft_preview": str(r.get("draft", ""))[:200]})
                elif score <= 50:
                    low_scores.append({"topic": r.get("topic"), "score": score, "critique": str(r.get("critique", ""))[:200]})

        return {
            "expert_id": expert_id,
            "total_runs": len(runs),
            "recent_runs": len(recent),
            "top_performers": high_scores[:3],
            "low_performers": low_scores[:3],
            "all_insights": all_insights,
        }
```

### Task 6: Write tests for MemoryAgent

**Files:** `tests/test_memory_agent.py` — test ingest, retrieve, empty state.

---

## Phase 3: A2A Protocol + Dispatcher

### Task 7: Create A2A protocol module

**Files:** `src/content_pipeline/a2a.py`

### Task 8: Create PipelineDispatcher

**Files:** `src/content_pipeline/dispatcher.py`

### Task 9: Write dispatcher tests

**Files:** `tests/test_dispatcher.py`

---

## Phase 4-6: Agent Migration (Strategist, Creator, Editor)

Each phase follows TDD: write tests first → migrate agent → verify.

### Phase 4: Strategist

### Phase 5: Creator

### Phase 6: Editor

---

## Phase 7: Memory Housekeeping

### Task: Implement conflict_scan, stale_detection, gap_hunt, graph_pruning

---

## Phase 8: Self-Reflection + Skill Auto-Update

### Task: Memory self_reflection cycle + skill patching

---

## Phase 9-10: API Layer + Observability

### Task: Update API endpoints, add new memory/skills endpoints
### Task: Add trace logging and metrics

---

## Verification

After all phases:
```bash
cd /root/content-producer && python -m pytest tests/ -v
```
Expected: all 54 existing tests + new tests pass.
