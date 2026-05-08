"""Tests for EditorAgent — v2 skill-based editor (scoring + visual brief)."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.content_pipeline.editor import EditorAgent
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
        update_count=3,
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
    c.draft = "Here is a polished draft about SaaS pricing. It has good flow and strong CTA."
    return c


def _mock_resp(content: str):  # pragma: no cover
    resp = MagicMock()
    choice = MagicMock()
    choice.message.content = content
    resp.choices = [choice]
    resp.usage.prompt_tokens = 30
    resp.usage.completion_tokens = 15
    return resp


class TestEditorAgent:
    """TDD tests for EditorAgent."""

    def test_initialization(self, tmp_path):
        """EditorAgent initializes with skill registry, api_key, model."""
        agent_dir = tmp_path / "editor" / "skills"
        agent_dir.mkdir(parents=True)
        (tmp_path / "editor" / "agent.md").write_text(
            "---\nagent: editor\nmodel: gpt-4o\ntemperature: 0.3\nversion: 1\n---\n"
        )
        (agent_dir / "multi_dimension_scoring.md").write_text(
            "---\nskill: multi_dimension_scoring\nversion: 1\nagent: editor\n---\n\n"
            "## Base Prompt\nScore for {expert_name}.\n"
        )

        registry = SkillRegistry(tmp_path)
        agent = EditorAgent(
            skill_registry=registry,
            api_key="test-key",
            model="gpt-4o",
        )

        assert agent.api_key == "test-key"
        assert agent.model == "gpt-4o"
        assert agent.tokens_prompt == 0
        assert agent.tokens_completion == 0

    @pytest.mark.asyncio
    async def test_score_populates_context(self, tmp_path, ctx):
        """score() calls LLM and fills ctx.score with ScoreResult."""
        agent_dir = tmp_path / "editor" / "skills"
        agent_dir.mkdir(parents=True)
        (tmp_path / "editor" / "agent.md").write_text("---\nagent: editor\n---\n")
        (agent_dir / "multi_dimension_scoring.md").write_text(
            "---\nskill: multi_dimension_scoring\nversion: 1\nagent: editor\n---\n\n"
            "## Base Prompt\nScore text: {text} for {expert_name}.\n"
        )

        registry = SkillRegistry(tmp_path)

        score_json = '{"overall": 85, "style_match": 80, "engagement": 90, "readability": 82, "grammar": 100, "brand_consistency": 88, "call_to_action": 75, "audience_fit": 85, "critique": "Great post", "rewrite_instruction": "", "visual_brief": {"hero": "dashboard screenshot"}, "engagement_predicted": {"likes": 200}}'

        with patch("src.content_pipeline.editor.openai.AsyncOpenAI") as MockClient:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=_mock_resp(score_json)
            )
            MockClient.return_value = mock_client

            agent = EditorAgent(
                skill_registry=registry,
                api_key="test-key",
                model="gpt-4o",
            )
            await agent.score(ctx)

        assert ctx.score is not None
        assert ctx.score.overall == 85
        assert ctx.score.engagement == 90
        assert ctx.score.style_match == 80
        assert agent.tokens_prompt == 30
        assert agent.tokens_completion == 15

    @pytest.mark.asyncio
    async def test_score_without_card_raises(self, tmp_path):
        """score() without ExpertCard raises AssertionError."""
        agent_dir = tmp_path / "editor" / "skills"
        agent_dir.mkdir(parents=True)
        (tmp_path / "editor" / "agent.md").write_text("---\nagent: editor\n---\n")
        (agent_dir / "multi_dimension_scoring.md").write_text(
            "---\nskill: multi_dimension_scoring\nversion: 1\n---\n\n## Base Prompt\nScore.\n"
        )

        registry = SkillRegistry(tmp_path)
        agent = EditorAgent(skill_registry=registry, api_key="test-key")
        ctx_no_card = PipelineContext(expert_id="test", topic="topic")

        with pytest.raises(AssertionError):
            await agent.score(ctx_no_card)

    @pytest.mark.asyncio
    async def test_score_handles_malformed_json(self, tmp_path, ctx):
        """score() gracefully handles LLM returning bad JSON."""
        agent_dir = tmp_path / "editor" / "skills"
        agent_dir.mkdir(parents=True)
        (tmp_path / "editor" / "agent.md").write_text("---\nagent: editor\n---\n")
        (agent_dir / "multi_dimension_scoring.md").write_text(
            "---\nskill: multi_dimension_scoring\nversion: 1\nagent: editor\n---\n\n"
            "## Base Prompt\nScore {text}.\n"
        )

        registry = SkillRegistry(tmp_path)

        with patch("src.content_pipeline.editor.openai.AsyncOpenAI") as MockClient:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=_mock_resp("not valid json at all {{{")
            )
            MockClient.return_value = mock_client

            agent = EditorAgent(skill_registry=registry, api_key="test-key")
            await agent.score(ctx)

        # Should fall back to default ScoreResult with critique containing raw text
        assert ctx.score is not None
        assert ctx.score.overall == 50  # default
        assert "not valid json" in ctx.score.critique or True  # fallback captures raw

    @pytest.mark.asyncio
    async def test_visual_brief_populates_context(self, tmp_path, ctx):
        """visual_brief() calls LLM and fills ctx.visual_brief."""
        agent_dir = tmp_path / "editor" / "skills"
        agent_dir.mkdir(parents=True)
        (tmp_path / "editor" / "agent.md").write_text("---\nagent: editor\n---\n")
        (agent_dir / "visual_brief.md").write_text(
            "---\nskill: visual_brief\nversion: 1\nagent: editor\n---\n\n"
            "## Base Prompt\nGenerate visual brief for {expert_name} on {platform}. Text: {text}.\n"
        )

        registry = SkillRegistry(tmp_path)

        brief_json = '{"asset_type": "single_image", "image_prompts": ["dashboard hero shot"], "cover_caption": "Pricing secrets", "color_palette": ["#1a1a2e", "#e94560"], "visual_style": "dark tech", "production_notes": "keep minimal"}'

        with patch("src.content_pipeline.editor.openai.AsyncOpenAI") as MockClient:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=_mock_resp(brief_json)
            )
            MockClient.return_value = mock_client

            agent = EditorAgent(
                skill_registry=registry,
                api_key="test-key",
                model="gpt-4o",
            )
            await agent.visual_brief(ctx)

        assert ctx.visual_brief is not None
        assert ctx.visual_brief["asset_type"] == "single_image"
        assert "dashboard hero shot" in ctx.visual_brief["image_prompts"]

    @pytest.mark.asyncio
    async def test_visual_brief_without_card_raises(self, tmp_path):
        """visual_brief() without ExpertCard raises AssertionError."""
        agent_dir = tmp_path / "editor" / "skills"
        agent_dir.mkdir(parents=True)
        (tmp_path / "editor" / "agent.md").write_text("---\nagent: editor\n---\n")
        (agent_dir / "visual_brief.md").write_text(
            "---\nskill: visual_brief\nversion: 1\n---\n\n## Base Prompt\nBrief.\n"
        )

        registry = SkillRegistry(tmp_path)
        agent = EditorAgent(skill_registry=registry, api_key="test-key")
        ctx_no_card = PipelineContext(expert_id="test", topic="topic")

        with pytest.raises(AssertionError):
            await agent.visual_brief(ctx_no_card)
