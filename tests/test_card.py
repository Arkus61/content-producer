
from src.expert_card.card import (
    ExpertCard, ToneOfVoice, Audience, ContentStrategy,
    PersonalityProfile, ExpertiseProfile, ProductProfile,
)


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


def test_card_with_profiles():
    """New profile fields work correctly."""
    card = ExpertCard(
        name="Test",
        personality=PersonalityProfile(
            values=["свобода", "честность"],
            traits=["целеустремлённый"],
            hobbies=["чтение", "спорт"],
        ),
        expertise_profile=ExpertiseProfile(
            mission="помогать людям",
            unique_skills=["AI", "маркетинг"],
            beliefs=["всегда учиться"],
        ),
        product=ProductProfile(
            name="Курс по AI",
            description="Обучение работе с нейросетями",
            problem="Люди не умеют использовать AI",
        ),
    )
    assert card.personality.values == ["свобода", "честность"]
    assert card.expertise_profile.mission == "помогать людям"
    assert card.product.name == "Курс по AI"


def test_card_to_markdown():
    card = ExpertCard(
        name="Test",
        profession="Dev",
        expertise=["Python"],
        personality=PersonalityProfile(values=["креативность"]),
        expertise_profile=ExpertiseProfile(mission="создавать"),
        product=ProductProfile(name="Сервис"),
    )
    md = card.to_markdown()
    assert "Test" in md
    assert "Dev" in md
    assert "Python" in md
    assert "Личность" in md
    assert "Экспертность" in md
    assert "Продукт" in md


def test_card_from_markdown():
    md = "# Эксперт: Тест\n**Профессия:** Dev"
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
        core_segment="предприниматели",
    )
    assert len(audience.pain_points) == 2
    assert audience.core_segment == "предприниматели"


def test_personality_profile():
    p = PersonalityProfile(
        values=["семья"],
        traits=["добрый"],
        childhood_dream="космонавт",
    )
    assert p.childhood_dream == "космонавт"
    assert p.family_background == ""  # default


def test_expertise_profile():
    ep = ExpertiseProfile(
        unique_skills=["Python"],
        metrics="10 лет опыта, 500+ клиентов",
    )
    assert len(ep.unique_skills) == 1
    assert ep.mistakes == []  # default


def test_product_profile():
    pr = ProductProfile(
        name="SaaS",
        problem="медленные процессы",
        secrets=["автоматизация"],
    )
    assert pr.guarantees == ""  # default
    assert len(pr.secrets) == 1


def test_card_defaults():
    card = ExpertCard(name="Simple")
    assert card.tone.style == "expert"
    assert card.expertise == []
    assert card.stories == []
    assert card.personality.values == []
    assert card.expertise_profile.unique_skills == []
    assert card.product.name == ""
