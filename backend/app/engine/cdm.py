"""
CDM Engine — Cognitive Diagnostic Model using the Answer Traps table.

On a wrong answer:
  1. Look up (question_id, option_label) in answer_traps.
  2. Return trap metadata for the orchestrator to execute.
"""

from typing import Optional
from sqlalchemy.orm import Session as DBSession
from app.models import AnswerTrap, Question


REMEDIAL_ACTIONS = {
    "Careless_Slip": "serve_same_level",
    "Calculation_Error": "serve_same_level",
    "Concept_Error": "go_down_grade",
    "Sign_Error": "go_prereq_skill",
    "Procedural_Error": "serve_same_level",
    "Reading_Error": "serve_same_level",   # handled by Twin diagnostic first
}


class TrapResult:
    def __init__(
        self,
        trap_type: str,
        skill_gap_id: Optional[str],
        misconception: Optional[str],
        misconception_detail: Optional[str],
        remedial_action: str,
        remedial_skill_id: Optional[str],
        remedial_grade: Optional[int],
    ):
        self.trap_type = trap_type
        self.skill_gap_id = skill_gap_id
        self.misconception = misconception
        self.misconception_detail = misconception_detail
        self.remedial_action = remedial_action
        self.remedial_skill_id = remedial_skill_id
        self.remedial_grade = remedial_grade

    def is_careless(self) -> bool:
        return self.trap_type in ("Careless_Slip", "Calculation_Error", "Procedural_Error")

    def is_concept_error(self) -> bool:
        return self.trap_type in ("Concept_Error", "Sign_Error")


def lookup_trap(
    db: DBSession, question_id: str, selected_option: str
) -> Optional[TrapResult]:
    """
    Retrieve the answer trap for a wrong selection.
    Returns None if no trap is configured for this option.
    """
    trap = (
        db.query(AnswerTrap)
        .filter(
            AnswerTrap.question_id == question_id,
            AnswerTrap.option_label == selected_option.upper(),
        )
        .first()
    )
    if trap is None:
        # Fallback — no trap data; treat as generic concept error
        return TrapResult(
            trap_type="Concept_Error",
            skill_gap_id=None,
            misconception="Unknown error",
            misconception_detail=None,
            remedial_action="go_down_grade",
            remedial_skill_id=None,
            remedial_grade=None,
        )

    return TrapResult(
        trap_type=trap.trap_type or "Concept_Error",
        skill_gap_id=trap.skill_gap_id,
        misconception=trap.misconception,
        misconception_detail=trap.misconception_detail,
        remedial_action=trap.remedial_action or REMEDIAL_ACTIONS.get(trap.trap_type, "go_down_grade"),
        remedial_skill_id=trap.remedial_skill_id,
        remedial_grade=trap.remedial_grade,
    )


def get_skills_tested_by_question(db: DBSession, question_id: str):
    """Return all skill_ids tested by this question (from q_matrix)."""
    from app.models import QMatrix
    rows = db.query(QMatrix).filter(QMatrix.question_id == question_id).all()
    return [r.skill_id for r in rows]
