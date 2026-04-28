
from src.producer_agent.agent import ProducerAgent
from src.producer_agent.strategy import build_strategy, CONTENT_PILLARS
from src.producer_agent.planner import generate_content_plan
from src.expert_card.card import ExpertCard

def _make_card():
    return ExpertCard(
        name="Test Expert",
        profession="Developer",
        expertise=["Python", "AI"],
    )

def test_producer_agent():
    card = _make_card()
    agent = ProducerAgent(card, api_key="test")
    strategy = agent.generate_strategy()
    assert "Test Expert" in strategy

def test_build_strategy():
    card = _make_card()
    s = build_strategy(card)
    assert s["expert"] == "Test Expert"
    assert "educational" in s["pillars"]

def test_content_plan():
    card = _make_card()
    plan = generate_content_plan(card, days=3)
    assert len(plan) <= 3
    for item in plan:
        assert "pillar" in item
        assert "topic" in item
        assert "day" in item

def test_content_pillars():
    assert len(CONTENT_PILLARS) == 4
    assert "promotional" in CONTENT_PILLARS
