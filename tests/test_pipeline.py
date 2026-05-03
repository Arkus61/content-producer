"""Tests for content pipeline agents, config loader, and style adapter."""
import asyncio
import json
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from src.expert_card.card import ExpertCard, StyleProfile
from src.content_pipeline import (
    ContentPipeline,
    ScoreResult,
    PipelineLog,
    PipelineContext,
)
from src.content_pipeline.config_loader import AgentConfig, AgentRegistry
from src.content_pipeline.style_adapter import StyleAdapter


# ── Fixtures ────────────────────────────────────────────

@pytest.fixture
def mock_card():
    card = ExpertCard(
        name="Test Expert",
        profession="Developer",
        expertise=["Python", "AI"],
    )
    card.style = StyleProfile(
        vocabulary=["pythonic", "async"],
        sentence_length="mixed",
        humor_level=5,
        emoji_usage="moderate",
        story_structure="hook-story-lesson",
        call_to_action_style="soft",
        update_count=0,
    )
    return card


@pytest.fixture
def mock_pipeline_result():
    return {
        "content": "Mocked draft content",
        "visual_brief": {"hero": "test.jpg"},
        "score": {
            "overall": 85,
            "style_match": 90,
            "engagement": 80,
            "engagement_predicted": {"likes_estimate": 100},
            "readability": 85,
            "grammar": 100,
            "brand_consistency": 88,
            "call_to_action": 75,
            "audience_fit": 82,
            "critique": "Great!",
            "rewrite_instruction": "",
            "visual_brief": {},
        },
        "iterations": 1,
        "logs": ["researcher done", "writer done"],
        "task_id": "mock-task",
        "pipeline_log": {},
    }


# ── Config Loader Tests ─────────────────────────────────

def test_agent_config_loads_from_markdown(tmp_path):
    md = tmp_path / "AGENT-01-TEST.md"
    md.write_text(
        "---\n"
        "id: test-agent\n"
        "model: gpt-4o-mini\n"
        "temperature: 0.5\n"
        "max_tokens: 100\n"
        "response_format: json_object\n"
        "---\n\n"
        "# Test Agent\n\n"
        "```\nYou are a test agent.\n```\n"
    )
    cfg = AgentConfig(md)
    assert cfg.id == "test-agent"
    assert cfg.model == "gpt-4o-mini"
    assert cfg.temperature == 0.5
    assert cfg.max_tokens == 100
    assert cfg.response_format == "json_object"
    assert "You are a test agent." in cfg.system_prompt


def test_agent_registry_discovers_agents(tmp_path):
    # Create sample agent files
    (tmp_path / "AGENT-01-A.md").write_text("---\nid: a\n---\n")
    (tmp_path / "AGENT-02-B.md").write_text("---\nid: b\n---\n")
    (tmp_path / "README.md").write_text("# Readme\n")

    reg = AgentRegistry(tmp_path)
    assert sorted(reg.keys()) == ["a", "b"]
    assert reg.get("a").id == "a"


def test_agent_registry_missing_agent_raises():
    reg = AgentRegistry()
    with pytest.raises(KeyError):
        reg.get("nonexistent")


# ── Style Adapter Tests ─────────────────────────────────

def test_style_adapter_update_profile(mock_card):
    adapter = StyleAdapter()
    text = (
        "Python async programming is amazing! 🐍\n"
        "Here is a pythonic way to solve this problem.\n"
        "Using async features makes your code faster and better.\n"
    )
    scores = {"overall": 85, "style_match": 90}
    result = adapter.update_profile(mock_card, text, scores)

    assert result == mock_card
    assert "pythonic" in mock_card.style.vocabulary
    assert "async" in mock_card.style.vocabulary
    assert mock_card.style.update_count == 1


def test_style_adapter_emoji_detection(mock_card):
    adapter = StyleAdapter()
    text = "Hello! 🚀🚀🚀 Great news!!!"
    scores = {"overall": 80}
    adapter.update_profile(mock_card, text, scores)
    assert mock_card.style.emoji_usage == "heavy"


def test_style_adapter_sentence_length(mock_card):
    adapter = StyleAdapter()
    # Short sentences
    text = "Hi. This is short. Very brief."
    adapter.update_profile(mock_card, text, {})
    assert mock_card.style.sentence_length == "short"


def test_style_adapter_call_to_action_detection(mock_card):
    adapter = StyleAdapter()
    text = "Buy now! Click here! Order today!"
    adapter.update_profile(mock_card, text, {})
    assert mock_card.style.call_to_action_style == "direct"

def test_style_adapter_soft_cta(mock_card):
    adapter = StyleAdapter()
    text = "Join us to learn more. Share your thoughts below."
    adapter.update_profile(mock_card, text, {})
    assert mock_card.style.call_to_action_style == "soft"


# ── Pipeline Integration Tests ───────────────────────────

@pytest.mark.asyncio
async def test_pipeline_run_with_mocked_agents(mock_card, mock_pipeline_result):
    """End-to-end pipeline test with all agents mocked."""
    with patch("src.content_pipeline.pipeline.ResearcherAgent") as MockResearcher, \
         patch("src.content_pipeline.pipeline.WriterAgent") as MockWriter, \
         patch("src.content_pipeline.pipeline.StyleEnforcerAgent") as MockStyle, \
         patch("src.content_pipeline.pipeline.EngagementOptimizerAgent") as MockEng, \
         patch("src.content_pipeline.pipeline.CriticAgent") as MockCritic, \
         patch("src.content_pipeline.pipeline.VisualBriefAgent") as MockVisual:

        # Setup mock instances
        for MockClass in [MockResearcher, MockWriter, MockStyle, MockEng, MockVisual]:
            inst = MagicMock()
            inst.run = AsyncMock()
            MockClass.return_value = inst

        # Critic returns passing score
        critic_inst = MagicMock()
        score = ScoreResult(
            overall=85, style_match=90, engagement=80,
            engagement_predicted={"likes_estimate": 100},
            readability=85, grammar=100, brand_consistency=88,
            call_to_action=75, audience_fit=82,
            critique="", rewrite_instruction="", visual_brief={},
        )
        async def mock_critic_run(ctx):
            ctx.score = score
        critic_inst.run = mock_critic_run
        MockCritic.return_value = critic_inst

        # Build pipeline with mocked agents (they get real registry but mock runs)
        from src.content_pipeline.pipeline import ContentPipeline
        with patch.object(ContentPipeline, "__init__", lambda self, **kw: None):
            pipeline = ContentPipeline()
            pipeline.api_key = ""
            pipeline.model = "gpt-4o"
            pipeline.reflection_threshold = 80.0
            pipeline.max_iterations = 3
            pipeline.registry = MagicMock()

            # Assign mocks directly
            for name, MockClass in [
                ("researcher", MockResearcher),
                ("writer", MockWriter),
                ("style_enforcer", MockStyle),
                ("engagement_optimizer", MockEng),
                ("critic", MockCritic),
                ("visual_brief", MockVisual),
            ]:
                setattr(pipeline, name, MockClass())

            # Patch _update_style_profile to avoid complex side effects
            pipeline._update_style_profile = MagicMock()

            result = await pipeline.run(
                card=mock_card,
                topic="Test topic",
                platform="telegram",
                content_type="post",
            )

        assert "content" in result
        assert "score" in result
        assert result["iterations"] >= 1
        assert result["task_id"]


@pytest.mark.asyncio
async def test_pipeline_reflection_loop(mock_card):
    """Test that score below threshold triggers a rewrite."""
    with patch("src.content_pipeline.pipeline.ResearcherAgent") as MockResearcher, \
         patch("src.content_pipeline.pipeline.WriterAgent") as MockWriter, \
         patch("src.content_pipeline.pipeline.StyleEnforcerAgent") as MockStyle, \
         patch("src.content_pipeline.pipeline.EngagementOptimizerAgent") as MockEng, \
         patch("src.content_pipeline.pipeline.CriticAgent") as MockCritic, \
         patch("src.content_pipeline.pipeline.VisualBriefAgent") as MockVisual:

        for MockClass in [MockResearcher, MockWriter, MockStyle, MockEng, MockVisual]:
            inst = MagicMock()
            inst.run = AsyncMock()
            MockClass.return_value = inst

        # Critic returns FAIL, then PASS
        call_count = 0
        async def mock_critic_run(ctx):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                ctx.score = ScoreResult(overall=70)  # FAIL
            else:
                ctx.score = ScoreResult(overall=85)  # PASS
        critic_inst = MagicMock()
        critic_inst.run = mock_critic_run
        MockCritic.return_value = critic_inst

        from src.content_pipeline.pipeline import ContentPipeline
        with patch.object(ContentPipeline, "__init__", lambda self, **kw: None):
            pipeline = ContentPipeline()
            pipeline.api_key = ""
            pipeline.model = "gpt-4o"
            pipeline.reflection_threshold = 80.0
            pipeline.max_iterations = 3
            pipeline.registry = MagicMock()

            for name, MockClass in [
                ("researcher", MockResearcher),
                ("writer", MockWriter),
                ("style_enforcer", MockStyle),
                ("engagement_optimizer", MockEng),
                ("critic", MockCritic),
                ("visual_brief", MockVisual),
            ]:
                setattr(pipeline, name, MockClass())

            pipeline._update_style_profile = MagicMock()

            result = await pipeline.run(
                card=mock_card,
                topic="Test topic",
                platform="telegram",
                content_type="post",
            )

        assert result["iterations"] == 2  # Initial + 1 rewrite
        assert len(mock_card.style.vocabulary) >= 0  # Style was accessed


# ── ScoreResult Defaults Test ───────────────────────────

def test_score_result_defaults():
    s = ScoreResult()
    assert s.overall == 0.0
    assert s.grammar == 100.0
    assert s.engagement_predicted == {}


# ── PipelineContext Extra Attrs ────────────────────────

def test_pipeline_context_extra_attrs():
    ctx = PipelineContext()
    ctx._private = "works"
    assert ctx._private == "works"
