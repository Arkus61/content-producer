from ..expert_card.card import ExpertCard

CONTENT_PILLARS = {
    "educational": "Обучающий контент — гайды, инструкции, разборы",
    "personal": "Личный бренд — истории, мнения, закулисье",
    "promotional": "Продающий контент — кейсы, отзывы, офферы",
    "engagement": "Вовлекающий контент — опросы, обсуждения, тренды",
}

def build_strategy(card: ExpertCard) -> dict:
    return {
        "expert": card.name,
        "pillars": list(CONTENT_PILLARS.keys()),
        "frequency": card.strategy.frequency or "3 поста/неделю",
        "platforms": card.strategy.platforms or ["telegram", "youtube"],
        "tone": card.tone.style,
    }
