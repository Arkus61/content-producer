
from src.interviewer.questions import (
    QUESTION_BANK, BLOCKS, SUBBLOCKS, SESSIONS,
    get_questions_by_block, get_questions_by_subblock,
    get_questions_for_session, get_next_question, get_question_by_id,
)
from src.interviewer.session import InterviewSession


def test_question_bank_300():
    """Must have exactly 300 questions."""
    assert len(QUESTION_BANK) == 300


def test_blocks():
    """Three blocks: personality, expertise, product."""
    blocks = set(q.block for q in QUESTION_BANK)
    assert blocks == {"personality", "expertise", "product"}


def test_block_counts():
    """Each block has exactly 100 questions."""
    for block in BLOCKS:
        qs = get_questions_by_block(block)
        assert len(qs) == 100, f"{block} has {len(qs)} questions, expected 100"


def test_subblocks():
    """Each block has multiple subblocks."""
    for block, subs in SUBBLOCKS.items():
        assert len(subs) >= 5, f"{block} has only {len(subs)} subblocks"


def test_get_questions_by_subblock():
    """get_questions_by_subblock returns correct questions."""
    qs = get_questions_by_subblock("personality", "hobbies")
    assert len(qs) == 11
    assert all(q.subblock == "hobbies" for q in qs)


def test_sessions():
    """All 5 sessions are defined and have questions."""
    for session_name in SESSIONS:
        qs = get_questions_for_session(session_name)
        assert len(qs) > 0, f"{session_name} has no questions"


def test_sessions_cover_all_questions():
    """All 300 questions are covered across sessions."""
    all_ids = set()
    for session_name in SESSIONS:
        qs = get_questions_for_session(session_name)
        all_ids.update(q.id for q in qs)
    assert len(all_ids) == 300, f"Sessions cover {len(all_ids)}/300 questions"


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
    assert "blocks" in p
    assert "personality" in p["blocks"]


def test_session_restricted():
    """Session-restricted interview covers only its questions."""
    s = InterviewSession(session_name="session_1")
    count = 0
    while not s.is_complete:
        q = s.get_next_question()
        if q:
            s.add_response(q.id, "test")
            count += 1
        else:
            break
    expected = len(get_questions_for_session("session_1"))
    assert count == expected


def test_get_question_by_id():
    q = get_question_by_id("p_01")
    assert q is not None
    assert q.text == "Чем вы любите заниматься в свободное время?"
    assert get_question_by_id("nonexistent") is None


def test_session_block_responses():
    """get_block_responses returns only responses for that block."""
    s = InterviewSession(session_name="session_1")
    while not s.is_complete:
        q = s.get_next_question()
        if q:
            s.add_response(q.id, "ответ")
        else:
            break
    p_resp = s.get_block_responses("personality")
    assert len(p_resp) > 0
    # session_1 is all personality
    assert len(p_resp) == len(get_questions_for_session("session_1"))
