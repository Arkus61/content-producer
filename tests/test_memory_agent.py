"""Tests for MemoryAgent — ingest, retrieve, housekeeping, self_reflection."""
import pytest
import json
import tempfile
from pathlib import Path
from src.content_pipeline.memory_agent import MemoryAgent


SAMPLE_RUN = {
    "task_id": "test-task-1",
    "topic": "SaaS pricing strategy",
    "platform": "telegram",
    "content_type": "post",
    "content": "Here is a draft about SaaS pricing...",
    "final_score": 85,
    "score": {"overall": 85, "style_match": 90, "engagement": 80},
    "iterations": 2,
}


@pytest.fixture
def memory_agent(tmp_path):
    return MemoryAgent(data_dir=tmp_path)


@pytest.mark.asyncio
async def test_ingest_run_creates_jsonl(memory_agent):
    result = await memory_agent.ingest_run("expert-1", SAMPLE_RUN)
    assert result["status"] == "ingested"
    assert result["nodes_extracted"] > 0
    assert result["edges_extracted"] > 0

    # Verify JSONL file exists
    jsonl = memory_agent.data_dir / "expert-1.jsonl"
    assert jsonl.exists()
    runs = memory_agent._read_jsonl("expert-1")
    assert len(runs) == 1
    assert runs[0]["topic"] == "SaaS pricing strategy"


@pytest.mark.asyncio
async def test_retrieve_context_returns_data(memory_agent):
    await memory_agent.ingest_run("expert-1", SAMPLE_RUN)
    await memory_agent.ingest_run("expert-1", {
        "task_id": "test-task-2",
        "topic": "SaaS pricing mistakes",
        "platform": "telegram",
        "content": "Low quality draft...",
        "final_score": 40,
        "iterations": 1,
    })

    ctx = await memory_agent.retrieve_context("expert-1", topic="pricing", limit=10)
    assert ctx["expert_id"] == "expert-1"
    assert ctx["total_runs"] == 2
    assert len(ctx["top_performers"]) >= 1
    assert len(ctx["low_performers"]) >= 1


@pytest.mark.asyncio
async def test_retrieve_context_empty(memory_agent):
    ctx = await memory_agent.retrieve_context("nonexistent")
    assert ctx["total_runs"] == 0
    assert ctx["top_performers"] == []


@pytest.mark.asyncio
async def test_conflict_scan(memory_agent):
    # Ingest two runs with same topic
    await memory_agent.ingest_run("expert-1", SAMPLE_RUN)
    await memory_agent.ingest_run("expert-1", SAMPLE_RUN)

    conflicts = await memory_agent.conflict_scan("expert-1")
    assert isinstance(conflicts, list)


@pytest.mark.asyncio
async def test_stale_detection(memory_agent):
    await memory_agent.ingest_run("expert-1", SAMPLE_RUN)
    stale = await memory_agent.stale_detection("expert-1", max_age_days=999)
    assert isinstance(stale, list)
    # Should be empty since edges just created
    assert len(stale) == 0


@pytest.mark.asyncio
async def test_gap_hunt(memory_agent):
    await memory_agent.ingest_run("expert-1", SAMPLE_RUN)
    gaps = await memory_agent.gap_hunt("expert-1")
    assert isinstance(gaps, list)


@pytest.mark.asyncio
async def test_self_reflection(memory_agent):
    await memory_agent.ingest_run("expert-1", SAMPLE_RUN)
    reflection = await memory_agent.self_reflection("expert-1")
    assert reflection["total_runs"] == 1
    assert reflection["health"] in ("good", "insufficient_data")
    assert "reflected_at" in reflection


@pytest.mark.asyncio
async def test_graph_pruning(memory_agent):
    await memory_agent.ingest_run("expert-1", SAMPLE_RUN)
    pruned = await memory_agent.graph_pruning("expert-1")
    assert pruned >= 0


@pytest.mark.asyncio
async def test_run_housekeeping_orchestrates_all_checks(memory_agent):
    """run_housekeeping() runs all 5 housekeeping tasks and returns a report."""
    await memory_agent.ingest_run("expert-1", SAMPLE_RUN)
    await memory_agent.ingest_run("expert-1", {
        "task_id": "test-task-2",
        "topic": "SaaS pricing mistakes",
        "platform": "telegram",
        "content": "Low quality draft...",
        "final_score": 40,
        "iterations": 1,
    })

    report = await memory_agent.run_housekeeping("expert-1")

    assert report["expert_id"] == "expert-1"
    assert "conflicts" in report
    assert "stale_edges" in report
    assert "gaps" in report
    assert "pruned_edges" in report
    assert "reflection" in report
    assert "timestamp" in report
    # reflection should have health
    assert report["reflection"]["health"] in ("good", "insufficient_data")
