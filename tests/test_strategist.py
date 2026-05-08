"""Tests for StrategistAgent — v2 skill-based strategist."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.content_pipeline.strategist import StrategistAgent
from src.content_pipeline.skill_loader import SkillRegistry
from src.content_pipeline.models import PipelineContext
from src.expert_card.card import ExpertCard, StyleProfile, ToneOfVoice, Audience


@pytest.fixture
def expert_card():
    card = ExpertCard(
        name="Test Expert",
        profession="SaaS founder",
        expertise=["pricing", "strategy"],
    )
    card.tone = ToneOfVoice(style="confident", format_pref="long", emoji_style="moderate")
    card.audience = Audience(
        core_segment="B2B founders",
        mass_segment="tech leads",
        pain_points=["pricing", "growth"],
    )
    card.style = StyleProfile(
        vocabulary=["SaaS", "growth"],
        sentence_length="mixed",
        humor_level=5,
        emoji_usage="moderate",
        story_structure="hook-story-lesson",
        call_to_action_style="soft",
        update_count=0,
    )
    return card


@pytest.fixture
def ctx(expert_card):
    c = PipelineContext(
        expert_id="test-expert-1",
        topic="How to price your SaaS",
        platform="telegram",
    )
    c._card = expert_card
    return c


class TestStrategistAgent:
    """TDD tests for StrategistAgent."""

    def test_initialization(self, tmp_path):
        """StrategistAgent initializes with skill registry and config."""
        # Setup minimal skill directory
        agent_dir = tmp_path / "strategist" / "skills"
        agent_dir.mkdir(parents=True)
        (tmp_path / "strategist" / "agent.md").write_text(
            "---\nagent: strategist\nmodel: gpt-4o-mini\ntemperature: 0.7\nversion: 1\n---\n"
        )
        (agent_dir / "audience_analysis.md").write_text(
            "---\nskill: audience_analysis\nversion: 1\nagent: strategist\n---\n\n## Base Prompt\nAnalyze audience for {expert_name}.\n"
        )

        registry = SkillRegistry(tmp_path)
        agent = StrategistAgent(
            skill_registry=registry,
            api_key="test-key",
            model="gpt-4o-mini",
        )

        assert agent.api_key == "test-key"
        assert agent.model == "gpt-4o-mini"
        assert agent.tokens_prompt == 0
        assert agent.tokens_completion == 0
        assert agent.skill_registry is registry

    @pytest.mark.asyncio
    async def test_run_calls_llm_and_populates_context(self, tmp_path, ctx):
        """run() loads skills, calls LLM, fills ctx.enriched + ctx.audience_summary."""
        # Setup skill directory
        agent_dir = tmp_path / "strategist" / "skills"
        agent_dir.mkdir(parents=True)
        (tmp_path / "strategist" / "agent.md").write_text(
            "---\nagent: strategist\nmodel: gpt-4o-mini\ntemperature: 0.7\nversion: 1\n---\n"
        )
        (agent_dir / "audience_analysis.md").write_text(
            "---\nskill: audience_analysis\nversion: 1\nagent: strategist\n---\n\n## Base Prompt\nAnalyze audience for {expert_name} in {niche}.\n"
        )
        (agent_dir / "hook_generation.md").write_text(
            "---\nskill: hook_generation\nversion: 1\nagent: strategist\n---\n\n## Base Prompt\nGenerate hooks for {expert_name} about {topic}.\n"
        )

        registry = SkillRegistry(tmp_path)

        # Mock OpenAI response
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = '{"audience_hook": "B2B founders struggle with pricing", "insights": ["price anchoring works"], "hooks": ["I raised prices 2x", "Why cheap kills your SaaS"]}'
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        with patch("src.content_pipeline.strategist.openai.AsyncOpenAI") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.chat.completions.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_client_instance

            agent = StrategistAgent(
                skill_registry=registry,
                api_key="test-key",
                model="gpt-4o-mini",
            )
            await agent.run(ctx)

        assert ctx.enriched is not None
        assert "audience_hook" in ctx.enriched
        assert ctx.audience_summary == "B2B founders struggle with pricing"
        assert agent.tokens_prompt == 100
        assert agent.tokens_completion == 50

    @pytest.mark.asyncio
    async def test_run_without_card_raises(self, tmp_path):
        """run() without ExpertCard attached raises AssertionError."""
        # Setup minimal skill dir
        agent_dir = tmp_path / "strategist" / "skills"
        agent_dir.mkdir(parents=True)
        (tmp_path / "strategist" / "agent.md").write_text(
            "---\nagent: strategist\nmodel: gpt-4o-mini\n---\n"
        )
        (agent_dir / "audience_analysis.md").write_text(
            "---\nskill: audience_analysis\nversion: 1\n---\n\n## Base Prompt\nTest.\n"
        )

        registry = SkillRegistry(tmp_path)
        agent = StrategistAgent(skill_registry=registry, api_key="test-key")

        ctx_no_card = PipelineContext(expert_id="test", topic="topic")
        with pytest.raises(AssertionError):
            await agent.run(ctx_no_card)

    @pytest.mark.asyncio
    async def test_run_skips_llm_when_no_skills_found(self, tmp_path, ctx):
        """run() gracefully handles empty skill directory."""
        agent_dir = tmp_path / "strategist" / "skills"
        agent_dir.mkdir(parents=True)
        (tmp_path / "strategist" / "agent.md").write_text(
            "---\nagent: strategist\nmodel: gpt-4o-mini\n---\n"
        )

        registry = SkillRegistry(tmp_path)
        agent = StrategistAgent(skill_registry=registry, api_key="test-key")
        await agent.run(ctx)

        # Should not crash, just leaves enriched empty
        assert ctx.enriched == {}
        assert ctx.audience_summary == ""
