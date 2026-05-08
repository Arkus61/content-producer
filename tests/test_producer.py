
import asyncio
from unittest.mock import patch, AsyncMock
from src.producer_agent.strategy import build_strategy, CONTENT_PILLARS
from src.producer_agent.planner import generate_content_plan
from src.expert_card.card import ExpertCard


def _make_card():
    return ExpertCard(
        name="Test Expert",
        profession="Developer",
        expertise=["Python", "AI"],
    )


def test_build_strategy():
    card = _make_card()
    s = build_strategy(card)
    assert s["expert"] == "Test Expert"
    assert "educational" in s["pillars"]

def test_content_plan():
    card = _make_card()
    mock_result = {
        "content": f"Mocked post for {card.profession}",
        "visual_brief": {},
        "score": {"overall": 85},
        "iterations": 1,
        "task_id": "mock-task",
        "pipeline_log": {},
        "trace": {"spans": []},
    }

    with patch("src.producer_agent.planner.PipelineDispatcher") as MockPipeline:
        instance = MockPipeline.return_value
        instance.run = AsyncMock(return_value=mock_result)
        plan = asyncio.run(generate_content_plan(card, days=3, api_key=""))

    assert len(plan) <= 3
    for item in plan:
        assert "pillar" in item
        assert "topic" in item
        assert "day" in item
        assert "pipeline_logs" in item  # injected by agent pipeline

def test_content_pillars():
    assert len(CONTENT_PILLARS) == 4
    assert "promotional" in CONTENT_PILLARS
