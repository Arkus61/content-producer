
from src.interviewer.questions import QUESTION_BANK, get_questions_by_category, get_next_question
from src.interviewer.session import InterviewSession

def test_question_bank_not_empty():
    assert len(QUESTION_BANK) >= 10

def test_categories():
    categories = set(q.category for q in QUESTION_BANK)
    assert "intro" in categories
    assert "expertise" in categories
    assert "audience" in categories

def test_get_questions_by_category():
    intro_qs = get_questions_by_category("intro")
    assert len(intro_qs) >= 2

def test_session_creation():
    s = InterviewSession(expert_name="Test")
    assert s.expert_name == "Test"
    assert not s.is_complete

def test_session_next_question():
    s = InterviewSession(expert_name="Test")
    q = s.get_next_question()
    assert q is not None
    assert q.id not in s.asked_questions

def test_session_progress():
    s = InterviewSession(expert_name="Test")
    p = s.get_progress()
    assert "answered" in p
    assert "total" in p
    assert "progress_percent" in p

def test_session_complete():
    s = InterviewSession(expert_name="Test")
    # Answer all questions
    while not s.is_complete:
        q = s.get_next_question()
        if q:
            s.add_response(q.id, "test answer")
        else:
            s.get_next_question()  # triggers is_complete
    assert s.is_complete
