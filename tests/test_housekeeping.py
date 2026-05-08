"""Phase 7 Housekeeping: deep TDD tests for conflict_scan, stale_detection, gap_hunt,
graph_pruning, self_reflection, run_housekeeping.

Goes beyond "doesn't crash" — verifies actual business logic:
- conflict_scan archives losers
- stale_detection finds old edges
- gap_hunt finds isolated nodes
- graph_pruning removes old tombstones
- self_reflection computes health, low_confidence_nodes, missing_links
- run_housekeeping orchestrates all five
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from src.content_pipeline.memory_agent import MemoryAgent


SAMPLE_RUN = {
    "task_id": "task-1",
    "topic": "SaaS pricing strategy",
    "platform": "telegram",
    "content_type": "post",
    "content": "Draft about SaaS pricing...",
    "final_score": 85,
    "score": {"overall": 85, "style_match": 90, "engagement": 80},
    "iterations": 2,
}


def _make_old_date(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


# ── Conflict Scan ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_conflict_scan_finds_duplicate_topic(tmp_path):
    """Two ingest_run calls with same topic → conflict found, loser archived."""
    agent = MemoryAgent(data_dir=tmp_path)

    run_a = dict(SAMPLE_RUN, task_id="run-a", final_score=88)
    run_b = dict(SAMPLE_RUN, task_id="run-b", final_score=42)

    await agent.ingest_run("expert-1", run_a)
    await agent.ingest_run("expert-1", run_b)

    conflicts = await agent.conflict_scan("expert-1")
    assert len(conflicts) > 0, "Should find at least one conflict"
    assert conflicts[0]["type"] == "conflict"
    assert conflicts[0]["action"] == "archive_loser"

    # Verify loser was archived
    loser_id = conflicts[0]["loser_id"]
    nodes = agent._read_jsonl("expert-1_nodes")
    loser = next(n for n in nodes if n["id"] == loser_id)
    assert loser["is_archived"] is True
    assert "archived_at" in loser


@pytest.mark.asyncio
async def test_conflict_scan_no_conflicts_on_different_topics(tmp_path):
    """Different topics → no conflicts."""
    agent = MemoryAgent(data_dir=tmp_path)

    await agent.ingest_run("expert-1", dict(SAMPLE_RUN, topic="growth hacking"))
    await agent.ingest_run("expert-1", dict(SAMPLE_RUN, topic="pricing strategy"))

    conflicts = await agent.conflict_scan("expert-1")
    assert conflicts == []


# ── Stale Detection ────────────────────────────────────────

@pytest.mark.asyncio
async def test_stale_detection_finds_old_edges(tmp_path):
    """Edge with last_confirmed_at older than max_age → stale."""
    agent = MemoryAgent(data_dir=tmp_path)

    # Ingest normally then manually age an edge
    await agent.ingest_run("expert-1", SAMPLE_RUN)
    edges = agent._read_jsonl("expert-1_edges")
    assert len(edges) > 0, "Should have edges after ingest"

    # Age first edge to 100 days ago
    edges[0]["last_confirmed_at"] = _make_old_date(100)
    agent._write_jsonl("expert-1_edges", edges)

    stale = await agent.stale_detection("expert-1", max_age_days=30)
    assert len(stale) > 0, "Should find the aged edge as stale"
    assert stale[0]["type"] == "stale_edge"
    assert stale[0]["edge_id"] == edges[0]["id"]


@pytest.mark.asyncio
async def test_stale_detection_skips_recent_edges(tmp_path):
    """Fresh edges are not stale."""
    agent = MemoryAgent(data_dir=tmp_path)
    await agent.ingest_run("expert-1", SAMPLE_RUN)

    stale = await agent.stale_detection("expert-1", max_age_days=30)
    assert stale == []


# ── Gap Hunt ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gap_hunt_finds_isolated_nodes(tmp_path):
    """Node with no connected edges → gap."""
    agent = MemoryAgent(data_dir=tmp_path)

    # Write an isolated node manually
    isolated_node = {
        "id": "isolated-1",
        "expert_id": "expert-1",
        "agent_id": "memory",
        "node_type": "topic",
        "label": "orphaned topic",
        "metadata": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_confirmed_at": datetime.now(timezone.utc).isoformat(),
        "evidence_count": 1,
        "confidence": 0.3,
        "is_archived": False,
    }
    agent._write_jsonl("expert-1_nodes", [isolated_node])

    gaps = await agent.gap_hunt("expert-1")
    assert len(gaps) == 1
    assert gaps[0]["type"] == "gap"
    assert gaps[0]["node_id"] == "isolated-1"
    assert "suggestion" in gaps[0]


@pytest.mark.asyncio
async def test_gap_hunt_skips_connected_nodes(tmp_path):
    """Nodes with edges are not gaps."""
    agent = MemoryAgent(data_dir=tmp_path)
    await agent.ingest_run("expert-1", SAMPLE_RUN)

    gaps = await agent.gap_hunt("expert-1")
    assert gaps == [], "All nodes should be connected via edges from ingest"


# ── Graph Pruning ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_graph_pruning_removes_old_tombstones(tmp_path):
    """Tombstoned edge older than tombstone_age → pruned."""
    agent = MemoryAgent(data_dir=tmp_path)
    await agent.ingest_run("expert-1", SAMPLE_RUN)

    edges = agent._read_jsonl("expert-1_edges")
    original_count = len(edges)
    assert original_count > 0

    # Mark first edge as tombstoned 100 days ago
    edges[0]["is_tombstone"] = True
    edges[0]["tombstoned_at"] = _make_old_date(100)
    agent._write_jsonl("expert-1_edges", edges)

    pruned = await agent.graph_pruning("expert-1", tombstone_age_days=30)
    assert pruned == 1

    # Verify it's gone
    remaining = agent._read_jsonl("expert-1_edges")
    assert len(remaining) == original_count - 1
    assert remaining[0]["id"] != edges[0]["id"]


@pytest.mark.asyncio
async def test_graph_pruning_keeps_recent_tombstones(tmp_path):
    """Tombstone younger than threshold stays."""
    agent = MemoryAgent(data_dir=tmp_path)
    await agent.ingest_run("expert-1", SAMPLE_RUN)

    edges = agent._read_jsonl("expert-1_edges")
    edges[0]["is_tombstone"] = True
    edges[0]["tombstoned_at"] = _make_old_date(1)  # 1 day old
    agent._write_jsonl("expert-1_edges", edges)

    pruned = await agent.graph_pruning("expert-1", tombstone_age_days=30)
    assert pruned == 0

    remaining = agent._read_jsonl("expert-1_edges")
    assert len(remaining) == len(edges), "Recent tombstone should stay"


# ── Self Reflection ────────────────────────────────────────

@pytest.mark.asyncio
async def test_self_reflection_returns_structured_health(tmp_path):
    """Reflection contains all expected keys with meaningful values."""
    agent = MemoryAgent(data_dir=tmp_path)
    await agent.ingest_run("expert-1", SAMPLE_RUN)
    await agent.ingest_run("expert-1", dict(SAMPLE_RUN, task_id="task-2",
                                            topic="Growth hacking", final_score=92))

    r = await agent.self_reflection("expert-1")

    assert r["expert_id"] == "expert-1"
    assert r["total_runs"] == 2
    assert r["total_nodes"] > 0
    assert r["total_edges"] > 0
    assert "reflected_at" in r
    assert r["health"] == "good"

    # Confidence audit: nodes should have confidence set
    nodes = agent._read_jsonl("expert-1_nodes")
    low_conf = [n for n in nodes if n.get("confidence", 0) < 0.4 and not n.get("is_archived")]
    assert r["low_confidence_nodes"] == len(low_conf)


@pytest.mark.asyncio
async def test_self_reflection_detects_missing_topic_links(tmp_path):
    """Two unlinked topic nodes → missing_links > 0."""
    agent = MemoryAgent(data_dir=tmp_path)

    # Write two topic nodes with no edge between them
    now = datetime.now(timezone.utc).isoformat()
    nodes = [
        {
            "id": "topic-1", "expert_id": "expert-1", "agent_id": "memory",
            "node_type": "topic", "label": "pricing", "metadata": {},
            "created_at": now, "last_confirmed_at": now,
            "evidence_count": 1, "confidence": 0.7, "is_archived": False,
        },
        {
            "id": "topic-2", "expert_id": "expert-1", "agent_id": "memory",
            "node_type": "topic", "label": "hiring", "metadata": {},
            "created_at": now, "last_confirmed_at": now,
            "evidence_count": 1, "confidence": 0.7, "is_archived": False,
        },
    ]
    agent._write_jsonl("expert-1_nodes", nodes)

    # No edges between them → missing_links = 1
    edges = [
        {
            "id": "edge-1", "expert_id": "expert-1",
            "from_node_id": "topic-1", "to_node_id": "score-1",
            "relation": "scored", "weight": 0.85,
            "evidence_count": 1, "created_at": now, "last_confirmed_at": now,
            "is_tombstone": False,
        },
    ]
    agent._write_jsonl("expert-1_edges", edges)

    r = await agent.self_reflection("expert-1")
    assert r["missing_topic_links"] == 1


# ── Run Housekeeping (orchestrator) ────────────────────────

@pytest.mark.asyncio
async def test_run_housekeeping_orchestrates_all_checks_with_meaningful_data(tmp_path):
    """Full orchestrated run → every section has meaningful content."""
    agent = MemoryAgent(data_dir=tmp_path)

    # Populate with 3 runs (same topic → conflict)
    await agent.ingest_run("expert-1", dict(SAMPLE_RUN, task_id="run-1", final_score=88))
    await agent.ingest_run("expert-1", dict(SAMPLE_RUN, task_id="run-2", final_score=42))
    await agent.ingest_run("expert-1", dict(SAMPLE_RUN, task_id="run-3", final_score=91))

    report = await agent.run_housekeeping("expert-1")

    assert report["expert_id"] == "expert-1"
    assert isinstance(report["conflicts"], list)
    assert isinstance(report["stale_edges"], list)
    assert isinstance(report["gaps"], list)
    assert isinstance(report["pruned_edges"], int)
    assert isinstance(report["reflection"], dict)
    assert "timestamp" in report

    # With 3 identical topics → at least one conflict
    assert len(report["conflicts"]) >= 1, "Expected conflicts from duplicate topic"

    # Reflection health should be good
    assert report["reflection"]["health"] == "good"
    assert report["reflection"]["total_runs"] >= 3
