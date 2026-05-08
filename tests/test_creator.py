"""Tests for CreatorAgent — v2 skill-based creator (draft → style → optimize)."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.content_pipeline.creator import CreatorAgent
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
    card.tone = ToneOfVoice(
        style="confident",
        format_pref="long",
        emoji_style="moderate",
        catchphrases=["think big", "ship fast"],
        stop_words=["obviously", "basically"],
    )
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
        update_count=5,
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
    c.enriched = {
        "audience_hook": "B2B founders struggle with pricing",
        "key_insights": ["anchor with value", "freemium kills conversion"],
        "narrative_angle": "contrarian: raise prices to grow",
    }
    return c


def _mock_openai_response(content: str):  # pragma: no cover — helper
    """Return a MagicMock simulating an OpenAI chat completion response."""
    resp = MagicMock()
    choice = MagicMock()
    choice.message.content = content
    resp.choices = [choice]
    resp.usage.prompt_tokens = 50
    resp.usage.completion_tokens = 25
    return resp


class TestCreatorAgent:
    """TDD tests for CreatorAgent."""

    def test_initialization(self, tmp_path):
        """CreatorAgent initializes with skill registry, api_key, model."""
        agent_dir = tmp_path / "creator" / "skills"
        agent_dir.mkdir(parents=True)
        (tmp_path / "creator" / "agent.md").write_text(
            "---\nagent: creator\nmodel: gpt-4o\ntemperature: 0.75\nversion: 1\n---\n"
        )
        (agent_dir / "draft_writing.md").write_text(
            "---\nskill: draft_writing\nversion: 1\nagent: creator\n---\n\n## Base Prompt\nWrite draft for {expert_name}.\n"
        )

        registry = SkillRegistry(tmp_path)
        agent = CreatorAgent(
            skill_registry=registry,
            api_key="test-key",
            model="gpt-4o",
        )

        assert agent.api_key == "test-key"
        assert agent.model == "gpt-4o"
        assert agent.tokens_prompt == 0
        assert agent.tokens_completion == 0

    @pytest.mark.asyncio
    async def test_run_writes_draft_and_applies_style_and_optimizes(self, tmp_path, ctx):
        """run() makes 3 LLM calls: draft → tone → platform optimize."""
        agent_dir = tmp_path / "creator" / "skills"
        agent_dir.mkdir(parents=True)
        (tmp_path / "creator" / "agent.md").write_text(
            "---\nagent: creator\nmodel: gpt-4o\n---\n"
        )
        (agent_dir / "draft_writing.md").write_text(
            "---\nskill: draft_writing\nversion: 1\nagent: creator\n---\n\n## Base Prompt\nWrite draft for {expert_name} about {topic}.\n"
        )
        (agent_dir / "tone_matching.md").write_text(
            "---\nskill: tone_matching\nversion: 1\nagent: creator\n---\n\n## Base Prompt\nRewrite {text} in {tone_style} tone.\n"
        )
        (agent_dir / "platform_optimization.md").write_text(
            "---\nskill: platform_optimization\nversion: 1\nagent: creator\n---\n\n## Base Prompt\nOptimize {text} for {platform}.\n"
        )

        registry = SkillRegistry(tmp_path)

        draft_text = "Here is a draft about SaaS pricing."
        styled_text = "Here is a confidently written draft about SaaS pricing."
        optimized_text = "🚀 Here is a Telegram-optimized draft about SaaS pricing."

        with patch("src.content_pipeline.creator.openai.AsyncOpenAI") as MockClient:
            mock_client = MagicMock()
            # First call = draft, second = style, third = optimize
            mock_client.chat.completions.create = AsyncMock(side_effect=[
                _mock_openai_response(draft_text),
                _mock_openai_response(styled_text),
                _mock_openai_response(optimized_text),
            ])
            MockClient.return_value = mock_client

            agent = CreatorAgent(
                skill_registry=registry,
                api_key="test-key",
                model="gpt-4o",
            )
            await agent.run(ctx)

        assert ctx.draft == optimized_text
        assert agent.tokens_prompt == 150  # 3 × 50
        assert agent.tokens_completion == 75  # 3 × 25

    @pytest.mark.asyncio
    async def test_run_without_card_raises(self, tmp_path):
        """run() without ExpertCard raises AssertionError."""
        agent_dir = tmp_path / "creator" / "skills"
        agent_dir.mkdir(parents=True)
        (tmp_path / "creator" / "agent.md").write_text("---\nagent: creator\n---\n")
        (agent_dir / "draft_writing.md").write_text(
            "---\nskill: draft_writing\nversion: 1\n---\n\n## Base Prompt\nTest.\n"
        )

        registry = SkillRegistry(tmp_path)
        agent = CreatorAgent(skill_registry=registry, api_key="test-key")

        ctx_no_card = PipelineContext(expert_id="test", topic="topic")
        with pytest.raises(AssertionError):
            await agent.run(ctx_no_card)

    @pytest.mark.asyncio
    async def test_run_with_missing_skills_still_works(self, tmp_path, ctx):
        """run() handles missing tone/platform skills gracefully — only drafts."""
        agent_dir = tmp_path / "creator" / "skills"
        agent_dir.mkdir(parents=True)
        (tmp_path / "creator" / "agent.md").write_text("---\nagent: creator\n---\n")
        # Only draft_writing exists — tone_matching and platform_optimization missing
        (agent_dir / "draft_writing.md").write_text(
            "---\nskill: draft_writing\nversion: 1\nagent: creator\n---\n\n## Base Prompt\nWrite for {expert_name}.\n"
        )

        registry = SkillRegistry(tmp_path)

        with patch("src.content_pipeline.creator.openai.AsyncOpenAI") as MockClient:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=_mock_openai_response("Draft only output.")
            )
            MockClient.return_value = mock_client

            agent = CreatorAgent(skill_registry=registry, api_key="test-key")
            await agent.run(ctx)

        # Only draft was produced
        assert ctx.draft == "Draft only output."

    @pytest.mark.asyncio
    async def test_run_no_skills_skips_llm(self, tmp_path, ctx):
        """run() with empty skills directory skips LLM entirely."""
        agent_dir = tmp_path / "creator" / "skills"
        agent_dir.mkdir(parents=True)
        (tmp_path / "creator" / "agent.md").write_text("---\nagent: creator\n---\n")

        registry = SkillRegistry(tmp_path)

        with patch("src.content_pipeline.creator.openai.AsyncOpenAI") as MockClient:
            agent = CreatorAgent(skill_registry=registry, api_key="test-key")
            await agent.run(ctx)
            # AsyncOpenAI should never be called
            MockClient.assert_not_called()

        assert ctx.draft == ""

    @pytest.mark.asyncio
    async def test_run_with_memory_notes(self, tmp_path, ctx):
        """run() injects memory_notes into draft prompt."""
        agent_dir = tmp_path / "creator" / "skills"
        agent_dir.mkdir(parents=True)
        (tmp_path / "creator" / "agent.md").write_text("---\nagent: creator\n---\n")
        (agent_dir / "draft_writing.md").write_text(
            "---\nskill: draft_writing\nversion: 1\nagent: creator\n---\n\n## Base Prompt\nWrite for {expert_name}. {memory_notes}\n"
        )

        ctx.memory_notes = ["Avoid pricing scare tactics", "Use contrarian angle"]

        registry = SkillRegistry(tmp_path)

        with patch("src.content_pipeline.creator.openai.AsyncOpenAI") as MockClient:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=_mock_openai_response("Great draft with memory.")
            )
            MockClient.return_value = mock_client

            agent = CreatorAgent(skill_registry=registry, api_key="test-key")
            await agent.run(ctx)

        assert "Great draft with memory" in ctx.draft
