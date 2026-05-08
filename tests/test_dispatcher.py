"""Tests for PipelineDispatcher v2."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.content_pipeline.dispatcher import PipelineDispatcher
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


def _mock_openai_response(content: str = "{}"):
    resp = MagicMock()
    choice = MagicMock()
    choice.message.content = content
    resp.choices = [choice]
    resp.usage.prompt_tokens = 10
    resp.usage.completion_tokens = 5
    return resp


def _setup_agent_skills(tmp_path, agent_name: str, skill_names: list[str]) -> None:
    agent_dir = tmp_path / agent_name
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.md").write_text(
        f"---\nagent: {agent_name}\nmodel: gpt-4o\nversion: 1\n---\n"
    )
    skills_dir = agent_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    for s in skill_names:
        (skills_dir / f"{s}.md").write_text(
            f"---\nskill: {s}\nversion: 1\nagent: {agent_name}\n---\n\n"
            f"## Base Prompt\nSkill prompt for {{expert_name}} about {{topic}}.\n"
        )


@pytest.mark.asyncio
async def test_dispatcher_initializes_with_skill_registry(tmp_path):
    for name in ["strategist", "creator", "editor", "memory"]:
        _setup_agent_skills(tmp_path, name, [])

    dispatcher = PipelineDispatcher(
        agents_dir=str(tmp_path),
        memory_data_dir=str(tmp_path / "memory"),
    )
    assert dispatcher.skill_registry is not None
    assert dispatcher.memory is not None


@pytest.mark.asyncio
async def test_full_pipeline_run_produces_result(tmp_path, expert_card):
    """End-to-end v2 pipeline with mocked LLM — no legacy code."""
    _setup_agent_skills(tmp_path, "strategist", ["audience_analysis", "hook_generation"])
    _setup_agent_skills(tmp_path, "creator", ["draft_writing", "tone_matching", "platform_optimization"])
    _setup_agent_skills(tmp_path, "editor", ["multi_dimension_scoring", "visual_brief"])
    _setup_agent_skills(tmp_path, "memory", [])

    score_json = '{"overall": 85, "style_match": 80, "engagement": 90, "rewrite_instruction": ""}'
    strat_resp = _mock_openai_response('{"audience_hook":"B2B founders", "hooks":["hook1"]}')
    content_resp = _mock_openai_response("Great content.")
    editor_resp = _mock_openai_response(score_json)
    visual_resp = _mock_openai_response('{"asset_type":"single_image"}')

    # Each agent gets its own mock client
    strat_client = MagicMock()
    strat_client.chat.completions.create = AsyncMock(return_value=strat_resp)
    creator_client = MagicMock()
    creator_client.chat.completions.create = AsyncMock(return_value=content_resp)
    editor_client = MagicMock()
    editor_client.chat.completions.create = AsyncMock(return_value=editor_resp)

    with patch("src.content_pipeline.strategist.openai.AsyncOpenAI", return_value=strat_client), \
         patch("src.content_pipeline.creator.openai.AsyncOpenAI", return_value=creator_client), \
         patch("src.content_pipeline.editor.openai.AsyncOpenAI", return_value=editor_client):

        dispatcher = PipelineDispatcher(
            api_key="test-key",
            agents_dir=str(tmp_path),
            memory_data_dir=str(tmp_path / "memory_data"),
        )
        result = await dispatcher.run(expert_card, topic="SaaS pricing", platform="telegram")

    # Pipeline completed without errors
    assert result is not None
    assert "content" in result
    assert "score" in result
    assert "iterations" in result
    assert "trace" in result
    assert result["iterations"] > 0
