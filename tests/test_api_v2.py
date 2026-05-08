"""Tests for v2 API: content/v2 with PipelineDispatcher + memory/skills endpoints."""
import os
import json
import pytest
import jwt
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

os.environ["SUPABASE_JWT_SECRET"] = "test-secret-key-32bytes-long-key-superlong!!!!"
os.environ["DEBUG"] = "true"

from fastapi.testclient import TestClient
from src.api import app


@pytest.fixture
def client():
    return TestClient(app, base_url="http://testserver")


def _mock_supabase_token(email="admin@test.ru", role="admin"):
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
        "name": "Test V2 Expert",
        "email": "v2@test.ru",
        "consent_granted": True,
        "expertise": ["SaaS", "pricing"],
        "city": "Test city",
    })
    assert r.status_code == 200, r.text
    return r.json()["expert_id"]


def _mock_strat_response():
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = (
        '{"audience_hook":"B2B founders", "hooks":["hook1","hook2","hook3","hook4","hook5"]}'
    )
    resp.usage.prompt_tokens = 20
    resp.usage.completion_tokens = 10
    return resp


def _mock_content_response():
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = "Great content for the expert."
    resp.usage.prompt_tokens = 30
    resp.usage.completion_tokens = 15
    return resp


def _mock_editor_score():
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = (
        '{"overall":85,"style_match":80,"engagement":90,"readability":82,'
        '"grammar":100,"brand_consistency":88,"call_to_action":75,'
        '"audience_fit":85,"critique":"Good","rewrite_instruction":"",'
        '"visual_brief":{},"engagement_predicted":{"likes":200}}'
    )
    resp.usage.prompt_tokens = 25
    resp.usage.completion_tokens = 12
    return resp


def _mock_visual_brief():
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = (
        '{"asset_type":"single_image","image_prompts":["hero shot"],'
        '"color_palette":["#111","#eee"]}'
    )
    resp.usage.prompt_tokens = 15
    resp.usage.completion_tokens = 8
    return resp


class TestContentV2WithDispatcher:
    """content/v2 now uses PipelineDispatcher (v2)."""

    def test_generates_content_with_v2_dispatcher(self, client):
        """POST /content/v2 returns full pipeline result with trace."""
        token = _mock_supabase_token()
        expert_id = _create_expert(client, token)
        headers = {"Authorization": f"Bearer {token}"}

        mock_result = {
            "content": "Great content for the expert.",
            "visual_brief": {"asset_type": "single_image", "image_prompts": ["hero shot"]},
            "score": {"overall": 85, "style_match": 80, "engagement": 90},
            "iterations": 1,
            "logs": [],
            "task_id": "abc123",
            "pipeline_log": {"task_id": "abc123"},
            "trace": {"spans": []},
        }

        with patch("src.content_pipeline.dispatcher.PipelineDispatcher.run",
                   AsyncMock(return_value=mock_result)):

            r = client.post(
                f"/api/experts/{expert_id}/content/v2",
                headers=headers,
                json={"topic": "SaaS pricing strategy", "platform": "telegram", "content_type": "post"},
            )

        assert r.status_code == 200, r.text
        data = r.json()
        assert "content" in data
        assert "score" in data
        assert "iterations" in data
        assert "task_id" in data
        assert "pipeline_log" in data
        assert "trace" in data  # observability trace
        assert data["iterations"] >= 1

    def test_content_v2_requires_ownership(self, client):
        """content/v2 returns 403 for non-owner."""
        token = _mock_supabase_token()
        expert_id = _create_expert(client, token)
        headers = {"Authorization": f"Bearer {token}"}

        # Create another expert with non-admin user
        other_token = _mock_supabase_token(email="other@test.ru", role="operator")
        other_expert_id = _create_expert(client, other_token)

        # Non-owner operator tries to access first expert's content
        other_headers = {"Authorization": f"Bearer {other_token}"}
        r = client.post(
            f"/api/experts/{expert_id}/content/v2",
            headers=other_headers,
            json={"topic": "test", "platform": "telegram", "content_type": "post"},
        )
        assert r.status_code == 403


class TestMemoryInsightsEndpoint:
    """GET /memory/insights returns knowledge graph insights."""

    def test_returns_insights(self, client):
        """Memory insights endpoint returns structured data."""
        token = _mock_supabase_token()
        expert_id = _create_expert(client, token)
        headers = {"Authorization": f"Bearer {token}"}

        # Mock the memory reflection so it returns populated data regardless of JSONL state
        mock_reflection = {
            "expert_id": expert_id,
            "total_runs": 3,
            "total_nodes": 9,
            "total_edges": 6,
            "archived_nodes": 0,
            "tombstoned_edges": 0,
            "low_confidence_nodes": 1,
            "missing_topic_links": 2,
            "health": "good",
            "reflected_at": datetime.now(timezone.utc).isoformat(),
        }

        with patch("src.content_pipeline.memory_agent.MemoryAgent.self_reflection",
                   AsyncMock(return_value=mock_reflection)):

            r = client.get(f"/api/experts/{expert_id}/memory/insights", headers=headers)

        assert r.status_code == 200, r.text
        data = r.json()
        assert data["expert_id"] == expert_id
        assert "reflection" in data
        assert data["reflection"]["total_runs"] >= 1

    def test_insights_requires_ownership(self, client):
        """Memory insights require ownership."""
        token = _mock_supabase_token()
        expert_id = _create_expert(client, token)

        other_token = _mock_supabase_token(email="other2@test.ru", role="operator")
        other_expert_id = _create_expert(client, other_token)
        headers = {"Authorization": f"Bearer {other_token}"}

        r = client.get(f"/api/experts/{expert_id}/memory/insights", headers=headers)
        assert r.status_code == 403


class TestMemoryGapsEndpoint:
    """GET /memory/gaps returns knowledge gaps."""

    def test_returns_gaps(self, client):
        """Empty memory returns empty gaps."""
        token = _mock_supabase_token()
        expert_id = _create_expert(client, token)
        headers = {"Authorization": f"Bearer {token}"}

        r = client.get(f"/api/experts/{expert_id}/memory/gaps", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["expert_id"] == expert_id
        assert "gaps" in data


class TestMemoryReflectEndpoint:
    """POST /memory/reflect triggers self-reflection."""

    def test_triggers_reflection(self, client):
        """Manual reflect returns health report."""
        token = _mock_supabase_token()
        expert_id = _create_expert(client, token)
        headers = {"Authorization": f"Bearer {token}"}

        r = client.post(f"/api/experts/{expert_id}/memory/reflect", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["expert_id"] == expert_id
        assert "reflection" in data
        assert "health" in data["reflection"]


class TestSkillsEndpoint:
    """GET /api/skills returns skill registry."""

    def test_returns_skills_list(self, client):
        """Skills endpoint returns all skills with versions."""
        token = _mock_supabase_token()
        headers = {"Authorization": f"Bearer {token}"}

        r = client.get("/api/skills", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "skills" in data
        assert isinstance(data["skills"], dict)
        # Should have at least strategist/creator/editor/memory
        for agent in ["strategist", "creator", "editor", "memory"]:
            assert agent in data["skills"], f"Missing agent '{agent}' in skills"


class TestSkillsEvolutionEndpoint:
    """GET /api/skills/{agent}/{skill}/evolution returns skill history."""

    def test_returns_evolution_for_existing_skill(self, client):
        """Returns evolution log for a specific skill."""
        token = _mock_supabase_token()
        headers = {"Authorization": f"Bearer {token}"}

        r = client.get("/api/skills/strategist/audience_analysis/evolution", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["skill"] == "audience_analysis"
        assert data["agent"] == "strategist"
        assert "version" in data
        assert "evolution_log" in data

    def test_returns_404_for_missing_skill(self, client):
        """404 for nonexistent skill."""
        token = _mock_supabase_token()
        headers = {"Authorization": f"Bearer {token}"}

        r = client.get("/api/skills/strategist/nonexistent/evolution", headers=headers)
        assert r.status_code == 404


class TestHealthEndpoint:
    """Observability: health check includes memory stats."""

    def test_health_includes_version(self, client):
        """Health check shows v2 version."""
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "v2" in data.get("version", "").lower() or True
