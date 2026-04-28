
from src.expert_card.card import ExpertCard, ToneOfVoice, Audience, ContentStrategy

def test_card_creation():
    card = ExpertCard(
        name="Иван Петров",
        nickname="ivan_expert",
        profession="Маркетолог",
        expertise=["SEO", "Content marketing", "SMM"],
        uvp="Помогаю бизнесу расти через контент",
    )
    assert card.name == "Иван Петров"
    assert card.profession == "Маркетолог"
    assert len(card.expertise) == 3

def test_card_to_markdown():
    card = ExpertCard(name="Test", profession="Dev", expertise=["Python"])
    md = card.to_markdown()
    assert "Test" in md
    assert "Dev" in md
    assert "Python" in md

def test_card_from_markdown():
    md = "# Эксперт: Тест\nПрофессия: Dev"
    card = ExpertCard.from_markdown(md)
    assert card.name == "Тест"

def test_tone_of_voice():
    tone = ToneOfVoice(style="humorous", emoji_style="many")
    assert tone.style == "humorous"
    assert tone.emoji_style == "many"

def test_audience():
    audience = Audience(
        demographics="25-40 лет, мужчины",
        pain_points=["нет времени", "нет денег"],
    )
    assert len(audience.pain_points) == 2

def test_card_defaults():
    card = ExpertCard(name="Simple")
    assert card.tone.style == "expert"
    assert card.expertise == []
    assert card.stories == []
