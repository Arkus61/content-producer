from dataclasses import dataclass, field
from .questions import (
    Question, get_next_question, get_questions_for_session,
    get_questions_by_subblock, QUESTION_BANK, BLOCKS, SUBBLOCKS, SESSIONS,
)


@dataclass
class InterviewSession:
    """Tracks a multi-block interview with 300 questions across 5 sessions."""
    expert_name: str = ""
    responses: dict[str, str] = field(default_factory=dict)
    asked_questions: list[str] = field(default_factory=list)
    current_block: str = "personality"
    current_subblock: str = "hobbies"
    is_complete: bool = False
    session_name: str = ""  # optional: restrict to a specific session

    def _advance_subblock(self) -> bool:
        """Move to next subblock. Returns True if moved, False if done."""
        subblocks = SUBBLOCKS.get(self.current_block, [])
        idx = subblocks.index(self.current_subblock) if self.current_subblock in subblocks else -1

        # Try next subblock in same block
        if idx < len(subblocks) - 1:
            self.current_subblock = subblocks[idx + 1]
            return True

        # Try next block
        block_idx = BLOCKS.index(self.current_block) if self.current_block in BLOCKS else -1
        if block_idx < len(BLOCKS) - 1:
            self.current_block = BLOCKS[block_idx + 1]
            self.current_subblock = SUBBLOCKS[self.current_block][0]
            return True

        # All done
        self.is_complete = True
        return False

    def get_next_question(self) -> Question | None:
        """Get the next unanswered question, advancing subblocks as needed."""
        # If restricted to a session, use session-scoped questions
        if self.session_name:
            session_questions = get_questions_for_session(self.session_name)
            asked = set(self.asked_questions)
            for q in session_questions:
                if q.id not in asked:
                    self.current_block = q.block
                    self.current_subblock = q.subblock
                    return q
            self.is_complete = True
            return None

        # Free-flow: iterate through all blocks/subblocks
        while True:
            q = get_next_question(self.current_block, self.current_subblock, set(self.asked_questions))
            if q:
                return q
            if not self._advance_subblock():
                return None

    def add_response(self, question_id: str, response: str):
        """Record an answer to a question."""
        self.responses[question_id] = response
        self.asked_questions.append(question_id)

    def get_progress(self) -> dict:
        """Return detailed progress stats."""
        total = len(QUESTION_BANK)
        if self.session_name:
            total = len(get_questions_for_session(self.session_name))
        answered = len(self.responses)

        # Per-block stats
        block_stats = {}
        for block in BLOCKS:
            block_qids = [q.id for q in QUESTION_BANK if q.block == block]
            block_answered = sum(1 for qid in block_qids if qid in self.responses)
            block_stats[block] = {
                "answered": block_answered,
                "total": len(block_qids),
                "percent": round(block_answered / len(block_qids) * 100) if block_qids else 0,
            }

        return {
            "session": self.session_name or "full",
            "block": self.current_block,
            "subblock": self.current_subblock,
            "answered": answered,
            "total": total,
            "progress_percent": round(answered / total * 100) if total else 0,
            "is_complete": self.is_complete,
            "blocks": block_stats,
        }

    def get_block_responses(self, block: str) -> dict[str, str]:
        """Get all responses for a specific block."""
        qids = {q.id for q in QUESTION_BANK if q.block == block}
        return {qid: resp for qid, resp in self.responses.items() if qid in qids}

    def get_subblock_responses(self, block: str, subblock: str) -> dict[str, str]:
        """Get all responses for a specific subblock."""
        qids = {q.id for q in QUESTION_BANK if q.block == block and q.subblock == subblock}
        return {qid: resp for qid, resp in self.responses.items() if qid in qids}
