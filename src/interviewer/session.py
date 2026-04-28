from dataclasses import dataclass, field
from .questions import Question, get_next_question, QUESTION_BANK

@dataclass
class InterviewSession:
    expert_name: str = ""
    responses: dict[str, str] = field(default_factory=dict)
    asked_questions: list[str] = field(default_factory=list)
    current_category: str = "intro"
    is_complete: bool = False
    
    CATEGORIES = ["intro", "expertise", "audience", "style", "goals", "story", "platform"]
    
    def get_next_question(self) -> Question | None:
        q = get_next_question(self.current_category, set(self.asked_questions))
        if q is None:
            idx = self.CATEGORIES.index(self.current_category)
            if idx < len(self.CATEGORIES) - 1:
                self.current_category = self.CATEGORIES[idx + 1]
                return self.get_next_question()
            self.is_complete = True
            return None
        return q
    
    def add_response(self, question_id: str, response: str):
        self.responses[question_id] = response
        self.asked_questions.append(question_id)
    
    def get_progress(self) -> dict:
        total = len(QUESTION_BANK)
        answered = len(self.responses)
        return {
            "category": self.current_category,
            "answered": answered,
            "total": total,
            "progress_percent": round(answered / total * 100),
            "is_complete": self.is_complete,
        }
