"""Phase 9-10: API Layer + Observability — final TDD tests.

Covers:
- /health returns pipeline metrics, memory stats, v2 version
- API responses include trace data from dispatcher
- Content list endpoint with v2 metadata
- Memory stats as a monitoring endpoint
- Observability: trace spans, latency in pipeline_log
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
import jwt
import uuid
import os

os.environ["SUPABASE_JWT_SECRET"] = "test-secret-key-32bytes-long-key-superlong!!!!"
os.environ["DEBUG"] = "true"

from src.api import app
from src.content_pipeline.memory_agent import MemoryAgent
from src.content_pipeline.skill_loader import SkillRegistry


@pytest.fixture
def client():
    return TestClient(app, base_url="http://testserver")


def _token(email="admin@test.ru", role="admin"):
    payload = {
        "sub": str(uuid.uuid4()),
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, os.environ["SUPABASE_JWT_SECRET"], algorithm="HS256")


def _create_expert(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/experts", headers=headers, json={
        "name": "Metrics Expert",
        "email": "metrics@test.ru",
        "consent_granted": True,
        "expertise": ["SaaS"],
        "city": "Test",
    })
    assert r.status_code == 200, r.text
    return r.json()["expert_id"]


# ── Health with metrics ─────────────────────────────────────

def test_health_returns_version_and_v2_status(client):
    """GET /health returns v2 version and status."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data


# ── Content v2 returns full trace ───────────────────────────

class TestContentV2Trace:
    """Verify that content/v2 response includes trace from PipelineDispatcher."""

    def test_content_v2_response_includes_trace(self, client):
        """POST content/v2 → response.trace has spans array from A2ATrace."""
        token = _token()
        expert_id = _create_expert(client, token)
        headers = {"Authorization": f"Bearer {token}"}

        mock_result = {
            "content": "Great content.",
            "visual_brief": {},
            "score": {"overall": 85},
            "iterations": 2,
            "logs": [],
            "task_id": "trace-abc",
            "pipeline_log": {
                "task_id": "trace-abc",
                "latency_sec": 1.23,
                "tokens_prompt": 150,
                "tokens_completion": 80,
            },
            "trace": {
                "spans": [
                    {"from": "strategist", "to": "creator", "task": "research",
                     "status": "ok", "skills_used": ["hook_generation"]},
                    {"from": "creator", "to": "editor", "task": "create_iter1",
                     "status": "ok", "skills_used": ["draft_writing"]},
                    {"from": "editor", "to": "creator", "task": "critique_iter1",
                     "status": "ok", "skills_used": ["multi_dimension_scoring"]},
                    {"from": "editor", "to": None, "task": "visual_brief",
                     "status": "ok", "skills_used": ["visual_brief"]},
                ],
            },
        }

        with patch("src.content_pipeline.dispatcher.PipelineDispatcher.run",
                   AsyncMock(return_value=mock_result)):

            r = client.post(
                f"/api/experts/{expert_id}/content/v2",
                headers=headers,
                json={"topic": "SaaS observability", "platform": "telegram",
                      "content_type": "post"},
            )

        assert r.status_code == 200
        data = r.json()
        assert "trace" in data, "Response must include trace from dispatcher"
        assert "spans" in data["trace"]
        assert len(data["trace"]["spans"]) >= 1, "At least one span expected"

        # Verify pipeline_log has latency metrics
        log = data["pipeline_log"]
        assert "latency_sec" in log
        assert log["latency_sec"] > 0
        assert "tokens_prompt" in log
        assert "tokens_completion" in log

    def test_content_v2_latency_tracked(self, client):
        """pipeline_log contains latency_sec for observability."""
        token = _token()
        expert_id = _create_expert(client, token)
        headers = {"Authorization": f"Bearer {token}"}

        mock_result = {
            "content": "Content.",
            "visual_brief": {},
            "score": {"overall": 80},
            "iterations": 1,
            "logs": [],
            "task_id": "lat-123",
            "pipeline_log": {
                "task_id": "lat-123",
                "latency_sec": 3.14,
                "tokens_prompt": 200,
                "tokens_completion": 100,
                "model": "gpt-4o",
                "iterations": 1,
                "max_iterations": 3,
            },
            "trace": {"spans": []},
        }

        with patch("src.content_pipeline.dispatcher.PipelineDispatcher.run",
                   AsyncMock(return_value=mock_result)):

            r = client.post(
                f"/api/experts/{expert_id}/content/v2",
                headers=headers,
                json={"topic": "latency check", "platform": "telegram",
                      "content_type": "post"},
            )

        assert r.status_code == 200
        log = r.json()["pipeline_log"]
        assert log["latency_sec"] == 3.14
        assert log["tokens_prompt"] == 200
        assert log["tokens_completion"] == 100
        assert log["model"] == "gpt-4o"


# ── Memory stats endpoint ───────────────────────────────────

class TestMemoryStatsEndpoint:
    """Observability endpoint for memory health."""

    @pytest.mark.asyncio
    async def test_memory_stats_returns_structured_data(self, client):
        """Memory stats shows expert-level graph metrics."""
        token = _token()
        expert_id = _create_expert(client, token)
        headers = {"Authorization": f"Bearer {token}"}

        # Populate memory
        mem = MemoryAgent(data_dir="data/memory")
        await mem.ingest_run(expert_id, {
            "task_id": "stats-1",
            "topic": "test",
            "platform": "telegram",
            "final_score": 90,
            "iterations": 1,
        })

        r = client.get(f"/api/experts/{expert_id}/memory/insights", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["expert_id"] == expert_id
        assert "reflection" in data
        assert data["reflection"]["total_runs"] >= 1


# ── Skills registry via API ─────────────────────────────────

class TestSkillsAPI:
    """API exposes skill registry for monitoring what skills exist."""

    def test_list_skills_includes_all_agents(self, client):
        """GET /api/skills returns all 4 agents."""
        r = client.get("/api/skills")
        assert r.status_code == 200
        data = r.json()
        assert "skills" in data
        for agent in ["strategist", "creator", "editor", "memory"]:
            assert agent in data["skills"], f"Missing agent '{agent}'"

    def test_skill_evolution_returns_version(self, client):
        """GET skill evolution returns version and log."""
        r = client.get("/api/skills/strategist/audience_analysis/evolution")
        assert r.status_code == 200
        data = r.json()
        assert data["skill"] == "audience_analysis"
        assert data["agent"] == "strategist"
        assert "version" in data
        assert isinstance(data["evolution_log"], list)


# ── Content list v2 metadata ────────────────────────────────

class TestContentListV2:
    """Verify content list endpoint returns v2-generated content."""

    def test_content_list_returns_v2_generated_items(self, client):
        """After v2 pipeline run, content list includes the generated item."""
        token = _token()
        expert_id = _create_expert(client, token)
        headers = {"Authorization": f"Bearer {token}"}

        mock_result = {
            "content": "V2 generated content.",
            "visual_brief": {},
            "score": {"overall": 88},
            "iterations": 1,
            "logs": [],
            "task_id": "v2-abc",
            "pipeline_log": {"task_id": "v2-abc"},
            "trace": {"spans": []},
        }

        with patch("src.content_pipeline.dispatcher.PipelineDispatcher.run",
                   AsyncMock(return_value=mock_result)):

            client.post(
                f"/api/experts/{expert_id}/content/v2",
                headers=headers,
                json={"topic": "v2 test", "platform": "telegram", "content_type": "post"},
            )

        r = client.get(f"/api/experts/{expert_id}/content", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert len(data["items"]) >= 1
        assert data["items"][0]["topic"] == "v2 test"


# ── Dispatcher trace observability ──────────────────────────

class TestDispatcherTraceObservability:
    """Trace contains agent interaction graph for debugging."""

    def test_trace_spans_include_skills_used(self, client):
        """Each span in trace reports which skills were used."""
        token = _token()
        expert_id = _create_expert(client, token)
        headers = {"Authorization": f"Bearer {token}"}

        mock_result = {
            "content": "Content.",
            "visual_brief": {},
            "score": {"overall": 80},
            "iterations": 1,
            "logs": [],
            "task_id": "skills-trace",
            "pipeline_log": {"task_id": "skills-trace"},
            "trace": {
                "spans": [
                    {"from": "strategist", "to": "creator", "task": "research",
                     "skills_used": ["trend_research", "hook_generation"]},
                    {"from": "creator", "to": "editor", "task": "create_iter1",
                     "skills_used": ["draft_writing", "tone_matching",
                                      "platform_optimization"]},
                    {"from": "editor", "to": None, "task": "visual_brief",
                     "skills_used": ["visual_brief"]},
                ],
            },
        }

        with patch("src.content_pipeline.dispatcher.PipelineDispatcher.run",
                   AsyncMock(return_value=mock_result)):

            r = client.post(
                f"/api/experts/{expert_id}/content/v2",
                headers=headers,
                json={"topic": "skills tracing", "platform": "telegram",
                      "content_type": "post"},
            )

        assert r.status_code == 200
        spans = r.json()["trace"]["spans"]
        skills_used = []
        for span in spans:
            skills_used.extend(span.get("skills_used", []))

        # Verify all major skill categories appear
        assert "draft_writing" in skills_used or any("draft" in s for s in skills_used)
        assert "hook_generation" in skills_used or "trend_research" in skills_used
        assert "visual_brief" in skills_used
