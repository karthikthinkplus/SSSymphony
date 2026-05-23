"""
Twin Question Diagnostic.

Triggers when a student fails a word problem:
  - Serve the equation_twin_id version (pure math, no narrative text)
  - Compare both responses to diagnose Reading Error vs. Math Concept Error

Logic:
  Word=Wrong, Twin=Correct  → Reading/Comprehension gap
  Word=Wrong, Twin=Wrong    → Math Concept gap (proceed with CDM)
"""

from typing import Optional
from sqlalchemy.orm import Session as DBSession
from app.models import Question


class TwinDiagnosticResult:
    READING_GAP = "reading_gap"
    MATH_GAP = "math_gap"
    NO_TWIN = "no_twin"

    def __init__(self, outcome: str, twin_question_id: Optional[str] = None):
        self.outcome = outcome
        self.twin_question_id = twin_question_id

    @property
    def is_reading_gap(self):
        return self.outcome == self.READING_GAP

    @property
    def is_math_gap(self):
        return self.outcome == self.MATH_GAP


def get_twin_question(db: DBSession, question_id: str) -> Optional[Question]:
    """Return the equation twin for a word problem, if one exists."""
    q = db.query(Question).filter(Question.question_id == question_id).first()
    if q is None or not q.equation_twin_id:
        return None
    return db.query(Question).filter(Question.question_id == q.equation_twin_id).first()


def evaluate_twin_result(twin_correct: bool) -> TwinDiagnosticResult:
    """
    Called after the twin probe response is received.
    The word problem was already answered incorrectly (trigger condition).

      twin_correct=True  → Reading gap (can solve the math, failed the words)
      twin_correct=False → Math gap (proceed with CDM remediation)
    """
    if twin_correct:
        return TwinDiagnosticResult(TwinDiagnosticResult.READING_GAP)
    else:
        return TwinDiagnosticResult(TwinDiagnosticResult.MATH_GAP)
