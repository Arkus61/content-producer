from ..expert_card.card import ExpertCard

class ProducerAgent:
    """AI-продюсер, который управляет контент-стратегией эксперта"""
    
    def __init__(self, expert_card: ExpertCard, api_key: str):
        self.card = expert_card
        self.api_key = api_key
    
    def generate_strategy(self) -> str:
        expertise_str = ", ".join(self.card.expertise[:3])
        return f"Стратегия для {self.card.name}: фокус на {expertise_str}"
    
    def get_content_plan(self, period: str = "week") -> list[dict]:
        return [
            {"type": "post", "platform": "telegram", "topic": "Введение в тему"},
            {"type": "video", "platform": "youtube", "topic": "Основы экспертизы"},
        ]
