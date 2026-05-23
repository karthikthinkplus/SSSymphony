"""
Master Orchestrator — get_next_question() loop.

Implements the full 8-step algorithm from Part 3 of the master prompt,
integrating IRT, CDM, BKT, DKT, and Twin Question diagnostic.
"""

import json
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session as DBSession

from app.models import (
    Session, Student, Question, Skill, BKTState, Response,
    KnowledgeGraph, AnswerTrap,
)
from app.engine import irt, cdm, bkt as bkt_engine, dkt, twin as twin_engine
from app.schemas import QuestionOut

MIN_QUESTIONS = 30
MAX_QUESTIONS = 40
GRADE_MIN = 5
GRADE_MAX = 10

# Skills ordered per grade — default topic progression
SKILL_TOPIC_ORDER = ["Arithmetic", "Algebra", "Geometry", "Statistics", "Probability"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _served_ids(session: Session) -> List[str]:
    if not session.questions_served:
        return []
    return [x for x in session.questions_served.split(",") if x]


def _add_served(session: Session, qid: str):
    served = _served_ids(session)
    if qid not in served:
        served.append(qid)
    session.questions_served = ",".join(served)


def _visited_skills(session: Session) -> List[str]:
    if not session.skills_visited:
        return []
    return [x for x in session.skills_visited.split(",") if x]


def _add_visited_skill(session: Session, sid: str):
    visited = _visited_skills(session)
    if sid not in visited:
        visited.append(sid)
    session.skills_visited = ",".join(visited)


def _log_traversal(session: Session, from_skill: str, from_grade: int,
                   to_skill: str, to_grade: int, reason: str):
    chain = []
    if session.prerequisite_chain:
        try:
            chain = json.loads(session.prerequisite_chain)
        except Exception:
            chain = []
    chain.append({
        "from_skill": from_skill,
        "from_grade": from_grade,
        "to_skill": to_skill,
        "to_grade": to_grade,
        "reason": reason,
        "at": datetime.utcnow().isoformat(),
    })
    session.prerequisite_chain = json.dumps(chain)


def _get_bkt_state(db: DBSession, student_id: str, skill_id: str) -> BKTState:
    state = (
        db.query(BKTState)
        .filter(BKTState.student_id == student_id, BKTState.skill_id == skill_id)
        .first()
    )
    if state is None:
        state = BKTState(
            student_id=student_id,
            skill_id=skill_id,
            p_mastery=0.10,
            attempts=0,
            last_updated=datetime.utcnow(),
        )
        db.add(state)
        db.flush()
    return state


def _fetch_question(
    db: DBSession,
    skill_id: str,
    grade: int,
    difficulty: str,
    exclude_ids: List[str],
    fallback=True,
) -> Optional[Question]:
    """
    Fetch an unseen question for the given skill/grade/difficulty.
    Tries exact grade match first, then falls back to any question for the skill.
    Grade filtering is secondary because the XLSX skill_id already encodes
    the correct grade range — filtering questions by grade_level further
    would over-restrict when skills span multiple grades.
    """
    difficulties = [difficulty]
    if fallback:
        full_order = ["easy", "medium", "hard"]
        idx = full_order.index(difficulty) if difficulty in full_order else 1
        if idx > 0:
            difficulties.append(full_order[idx - 1])
        if idx < 2:
            difficulties.append(full_order[idx + 1])

    grades_to_try = [grade]
    if fallback:
        if grade > GRADE_MIN:
            grades_to_try.append(grade - 1)
        if grade < GRADE_MAX:
            grades_to_try.append(grade + 1)

    # Try with grade + difficulty filters first
    for diff in difficulties:
        for g in grades_to_try:
            q = (
                db.query(Question)
                .filter(
                    Question.primary_skill_id == skill_id,
                    Question.grade_level == g,
                    Question.difficulty_band == diff,
                    ~Question.question_id.in_(exclude_ids or ["__none__"]),
                )
                .first()
            )
            if q:
                return q

    # Relax grade filter — try any grade for the skill + difficulty
    for diff in difficulties:
        q = (
            db.query(Question)
            .filter(
                Question.primary_skill_id == skill_id,
                Question.difficulty_band == diff,
                ~Question.question_id.in_(exclude_ids or ["__none__"]),
            )
            .first()
        )
        if q:
            return q

    # Last resort — any question for the skill not yet served
    q = (
        db.query(Question)
        .filter(
            Question.primary_skill_id == skill_id,
            ~Question.question_id.in_(exclude_ids or ["__none__"]),
        )
        .first()
    )
    return q


def _fetch_question_by_id(db: DBSession, question_id: str) -> Optional[Question]:
    return db.query(Question).filter(Question.question_id == question_id).first()


def _get_prerequisite_skill(db: DBSession, skill_id: str) -> Optional[Skill]:
    """Return the first prerequisite skill from the knowledge graph."""
    edge = (
        db.query(KnowledgeGraph)
        .filter(KnowledgeGraph.child_skill_id == skill_id)
        .first()
    )
    if edge:
        return db.query(Skill).filter(Skill.skill_id == edge.parent_skill_id).first()
    return None


def _grade_filter(grade: int):
    """Return a SQLAlchemy filter that matches skills whose grade_level contains `grade`.

    Handles both exact ('7') and range ('7-8', '5-6') formats stored in the XLSX.
    """
    from sqlalchemy import or_, cast, String
    grade_str = str(grade)
    return or_(
        Skill.grade_level == grade_str,                     # exact: "7"
        Skill.grade_level.like(f"{grade_str}-%"),           # range start: "7-8"
        Skill.grade_level.like(f"%-{grade_str}"),           # range end: "6-7"
        Skill.grade_level.like(f"%/{grade_str}/%"),         # slash-separated list
        Skill.grade_level.like(f"{grade_str}/%"),
        Skill.grade_level.like(f"/{grade_str}"),
    )


def _get_next_skill_in_grade(db: DBSession, session: Session) -> Optional[Skill]:
    """Get the next unvisited skill in the student's selected grade."""
    visited = _visited_skills(session)
    skill = (
        db.query(Skill)
        .filter(
            _grade_filter(session.selected_grade),
            ~Skill.skill_id.in_(visited or ["__none__"]),
        )
        .order_by(Skill.topic_area, Skill.skill_id)
        .first()
    )
    return skill


def _get_first_skill(db: DBSession, grade: int) -> Optional[Skill]:
    """Get the first skill (by topic order) for a given grade (handles range labels)."""
    skill = (
        db.query(Skill)
        .filter(_grade_filter(grade))
        .order_by(Skill.topic_area, Skill.skill_id)
        .first()
    )
    return skill


def _question_to_schema(q: Question, db: DBSession, session: Session,
                         is_twin: bool = False) -> QuestionOut:
    served = _served_ids(session)
    skill = db.query(Skill).filter(Skill.skill_id == q.primary_skill_id).first()
    return QuestionOut(
        question_id=q.question_id,
        question_text=q.question_text,
        question_type=q.question_type or "MCQ",
        word_problem_flag=q.word_problem_flag or False,
        grade_level=q.grade_level or session.current_grade,
        difficulty_band=q.difficulty_band or session.current_difficulty,
        skill_name=skill.skill_name if skill else "Unknown",
        topic_area=skill.topic_area if skill else "General",
        option_a=q.option_a,
        option_b=q.option_b,
        option_c=q.option_c,
        option_d=q.option_d,
        question_number=len(served) + 1,
        is_twin_probe=is_twin,
    )


def _get_skill_for_review(db: DBSession, session: Session) -> Optional[Skill]:
    """
    Get a skill in the student's selected grade for review when all skills have been visited
    but the minimum question count has not been reached.
    Prioritizes skills with the lowest BKT mastery score.
    """
    all_skills = (
        db.query(Skill)
        .filter(_grade_filter(session.selected_grade))
        .all()
    )
    if not all_skills:
        return None
    
    # Sort skills by their current mastery probability (lowest first)
    skills_with_mastery = []
    for s in all_skills:
        state = _get_bkt_state(db, session.student_id, s.skill_id)
        skills_with_mastery.append((s, state.p_mastery))
    
    skills_with_mastery.sort(key=lambda x: x[1])
    return skills_with_mastery[0][0]


def _check_session_complete(db: DBSession, session: Session) -> bool:
    """Check if the session should end."""
    served_count = len(_served_ids(session))
    
    # Under no circumstances does the session end before MIN_QUESTIONS
    if served_count < MIN_QUESTIONS:
        return False
        
    if served_count >= MAX_QUESTIONS:
        return True
        
    # Check if all grade skills visited and mastered
    all_skills = (
        db.query(Skill)
        .filter(_grade_filter(session.selected_grade))
        .all()
    )
    visited = _visited_skills(session)
    if all(s.skill_id in visited for s in all_skills):
        return True
    return False


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def get_next_question(
    db: DBSession,
    session: Session,
    last_response: Optional[Response],
) -> Optional[QuestionOut]:
    """
    Master next-question-selection loop.
    Returns the next QuestionOut, or None if the session is complete.
    """
    student_id = session.student_id
    exclude = _served_ids(session)

    # -----------------------------------------------------------------------
    # Initialisation — no response yet
    # -----------------------------------------------------------------------
    if last_response is None:
        skill = _get_first_skill(db, session.selected_grade)
        if skill is None:
            return None
        q = _fetch_question(db, skill.skill_id, session.selected_grade, "medium", exclude)
        if q is None:
            return None
        session.current_skill_id = skill.skill_id
        session.current_grade = session.selected_grade
        session.current_difficulty = "medium"
        _add_visited_skill(session, skill.skill_id)
        _add_served(session, q.question_id)
        db.commit()
        return _question_to_schema(q, db, session)

    # -----------------------------------------------------------------------
    # Extract last response context
    # -----------------------------------------------------------------------
    is_correct = last_response.is_correct
    question_id = last_response.question_id
    current_q = _fetch_question_by_id(db, question_id)
    trap_result = None
    engine_action = "standard_progression"

    # -----------------------------------------------------------------------
    # Step 1 — CDM: Identify trap if wrong
    # -----------------------------------------------------------------------
    if not is_correct:
        trap_result = cdm.lookup_trap(db, question_id, last_response.selected_option)

        # Update response record with trap info
        last_response.trap_type = trap_result.trap_type
        last_response.skill_gap_id = trap_result.skill_gap_id
        last_response.misconception = trap_result.misconception

        # -----------------------------------------------------------------------
        # Step 2 — Twin Question probe for word problems
        # -----------------------------------------------------------------------
        if (
            current_q
            and current_q.word_problem_flag
            and not session.twin_probe_pending
            and not last_response.twin_probe
        ):
            twin_q = twin_engine.get_twin_question(db, question_id)
            if twin_q:
                session.twin_probe_pending = True
                session.twin_origin_question_id = question_id
                _add_served(session, twin_q.question_id)
                db.commit()
                return _question_to_schema(twin_q, db, session, is_twin=True)

    # Handle twin probe result
    if session.twin_probe_pending and last_response.twin_probe:
        session.twin_probe_pending = False
        twin_correct = is_correct
        if twin_correct:
            # Reading/Comprehension gap — don't regress grade
            last_response.trap_type = "Reading_Error"
            engine_action = "reading_gap_detected"
            # Continue at same level
            q = _fetch_question(
                db, session.current_skill_id, session.current_grade,
                session.current_difficulty, _served_ids(session)
            )
            if q:
                _add_served(session, q.question_id)
                db.commit()
                return _question_to_schema(q, db, session)
        # Both wrong — fall through to CDM remediation with original trap
        trap_result = cdm.lookup_trap(
            db, session.twin_origin_question_id, last_response.selected_option
        )

    # -----------------------------------------------------------------------
    # Step 3 — Execute CDM remedial action (only on wrong answers)
    # -----------------------------------------------------------------------
    if not is_correct and trap_result:
        action = trap_result.remedial_action

        if action == "serve_same_level":
            engine_action = "retry_same_level"
            session.consecutive_failures += 1
            session.consecutive_correct = 0
            q = _fetch_question(
                db, session.current_skill_id, session.current_grade,
                session.current_difficulty, _served_ids(session)
            )
            if q:
                _add_served(session, q.question_id)
                db.commit()
                return _question_to_schema(q, db, session)

        elif action == "go_down_grade":
            new_grade = max(session.current_grade - 1, GRADE_MIN)
            target_skill_id = trap_result.remedial_skill_id or session.current_skill_id
            engine_action = f"go_down_grade_{new_grade}"
            _log_traversal(
                session, session.current_skill_id, session.current_grade,
                target_skill_id, new_grade, f"CDM:{trap_result.trap_type}"
            )
            session.current_grade = new_grade
            session.current_skill_id = target_skill_id
            session.current_difficulty = "easy"
            session.consecutive_failures += 1
            session.consecutive_correct = 0
            q = _fetch_question(db, target_skill_id, new_grade, "easy", _served_ids(session))
            if q:
                _add_served(session, q.question_id)
                db.commit()
                return _question_to_schema(q, db, session)

        elif action == "go_prereq_skill":
            prereq = _get_prerequisite_skill(db, session.current_skill_id)
            if prereq:
                engine_action = f"traverse_to_prereq_{prereq.skill_id}"
                _log_traversal(
                    session, session.current_skill_id, session.current_grade,
                    prereq.skill_id, int(prereq.grade_level or GRADE_MIN),
                    f"CDM:{trap_result.trap_type}"
                )
                session.current_skill_id = prereq.skill_id
                session.current_grade = int(prereq.grade_level or GRADE_MIN)
                session.current_difficulty = "easy"
                _add_visited_skill(session, prereq.skill_id)
                session.consecutive_failures += 1
                session.consecutive_correct = 0
                q = _fetch_question(
                    db, prereq.skill_id, session.current_grade, "easy", _served_ids(session)
                )
                if q:
                    _add_served(session, q.question_id)
                    db.commit()
                    return _question_to_schema(q, db, session)

        elif action == "flag_review":
            engine_action = "flagged_for_review"
            # Continue to next topic
            next_skill = _get_next_skill_in_grade(db, session)
            if next_skill:
                session.current_skill_id = next_skill.skill_id
                session.current_difficulty = "medium"
                _add_visited_skill(session, next_skill.skill_id)
                q = _fetch_question(
                    db, next_skill.skill_id, session.current_grade,
                    "medium", _served_ids(session)
                )
                if q:
                    _add_served(session, q.question_id)
                    db.commit()
                    return _question_to_schema(q, db, session)

    # -----------------------------------------------------------------------
    # Step 4 — BKT Update
    # -----------------------------------------------------------------------
    bkt_state = _get_bkt_state(db, student_id, session.current_skill_id)
    old_p = bkt_state.p_mastery
    new_p = bkt_engine.bkt_update(old_p, is_correct)
    bkt_state.p_mastery = new_p
    bkt_state.attempts += 1
    bkt_state.last_updated = datetime.utcnow()

    # Step 5 — IRT θ Update
    old_theta = session.current_theta
    session.current_theta = irt.update_theta_mle(
        old_theta, is_correct, session.current_difficulty
    )

    # Step 6 — Mastery Check
    if bkt_engine.is_mastered(new_p):
        engine_action = "mastered_advance"
        next_skill = _get_next_skill_in_grade(db, session)
        if next_skill is None:
            # All skills mastered — check if we reached min questions
            if len(_served_ids(session)) < MIN_QUESTIONS:
                target_skill = _get_skill_for_review(db, session)
                if target_skill:
                    session.current_skill_id = target_skill.skill_id
                    session.current_grade = session.selected_grade
                    session.current_difficulty = "medium"
                    session.consecutive_failures = 0
                    session.consecutive_correct = 0
                    q = _fetch_question(
                        db, target_skill.skill_id, session.current_grade,
                        "medium", _served_ids(session)
                    )
                    if q:
                        _add_served(session, q.question_id)
                        db.commit()
                        return _question_to_schema(q, db, session)
            # If no question was found or we met the min length, end session
            session.status = "completed"
            session.ended_at = datetime.utcnow()
            db.commit()
            return None
        session.current_skill_id = next_skill.skill_id
        session.current_grade = session.selected_grade
        session.current_difficulty = "medium"
        session.consecutive_failures = 0
        session.consecutive_correct = 0
        _add_visited_skill(session, next_skill.skill_id)
        q = _fetch_question(
            db, next_skill.skill_id, session.current_grade,
            "medium", _served_ids(session)
        )
        if q:
            _add_served(session, q.question_id)
            db.commit()
            return _question_to_schema(q, db, session)

    if bkt_engine.is_foundational_gap(new_p, bkt_state.attempts):
        prereq = _get_prerequisite_skill(db, session.current_skill_id)
        if prereq and prereq.skill_id not in _visited_skills(session):
            engine_action = f"foundational_gap_traverse_{prereq.skill_id}"
            _log_traversal(
                session, session.current_skill_id, session.current_grade,
                prereq.skill_id, int(prereq.grade_level or GRADE_MIN),
                "BKT:FoundationalGap"
            )
            session.current_skill_id = prereq.skill_id
            session.current_grade = max(int(prereq.grade_level or GRADE_MIN), GRADE_MIN)
            session.current_difficulty = "easy"
            _add_visited_skill(session, prereq.skill_id)
            session.consecutive_failures = 0
            q = _fetch_question(
                db, prereq.skill_id, session.current_grade, "easy", _served_ids(session)
            )
            if q:
                _add_served(session, q.question_id)
                db.commit()
                return _question_to_schema(q, db, session)

    # Step 7 — DKT propagation
    dkt.propagate(db, student_id, session.current_skill_id, old_p, new_p)

    # Step 7b — Lucky Guess Guard
    if bkt_engine.is_lucky_guess(old_p, is_correct):
        session.pending_confirmation = True
        engine_action = "lucky_guess_confirmation"
        q = _fetch_question(
            db, session.current_skill_id, session.current_grade,
            session.current_difficulty, _served_ids(session)
        )
        if q:
            _add_served(session, q.question_id)
            db.commit()
            return _question_to_schema(q, db, session)

    session.pending_confirmation = False

    # -----------------------------------------------------------------------
    # Step 8 — Standard Progression
    # -----------------------------------------------------------------------
    if is_correct:
        session.consecutive_correct += 1
        session.consecutive_failures = 0

        # Cross-grade traversal rule: 2 consecutive correct → escalate
        new_difficulty = irt.escalate_difficulty(session.current_difficulty)

        # If already at hard and 2+ correct streak, check if we've done ≥1 at each band
        if (
            session.consecutive_correct >= 2
            and session.current_difficulty == "hard"
        ):
            engine_action = "advance_topic"
            next_skill = _get_next_skill_in_grade(db, session)
            if next_skill:
                session.current_skill_id = next_skill.skill_id
                session.current_difficulty = "medium"
                session.consecutive_correct = 0
                _add_visited_skill(session, next_skill.skill_id)
                q = _fetch_question(
                    db, next_skill.skill_id, session.current_grade,
                    "medium", _served_ids(session)
                )
                if q:
                    _add_served(session, q.question_id)
                    db.commit()
                    return _question_to_schema(q, db, session)
        else:
            session.current_difficulty = new_difficulty
            engine_action = f"escalate_to_{new_difficulty}"
    else:
        session.consecutive_correct = 0
        session.consecutive_failures += 1
        new_difficulty = irt.reduce_difficulty(session.current_difficulty)

        # Cross-grade traversal: 2 consecutive failures at easy
        if session.consecutive_failures >= 2 and session.current_difficulty == "easy":
            prereq = _get_prerequisite_skill(db, session.current_skill_id)
            if prereq and prereq.skill_id not in _visited_skills(session):
                engine_action = f"cross_grade_traverse_{prereq.skill_id}"
                _log_traversal(
                    session, session.current_skill_id, session.current_grade,
                    prereq.skill_id, int(prereq.grade_level or GRADE_MIN),
                    "IRT:ConsecutiveFailuresAtEasy"
                )
                session.current_skill_id = prereq.skill_id
                session.current_grade = max(int(prereq.grade_level or GRADE_MIN), GRADE_MIN)
                session.current_difficulty = "easy"
                _add_visited_skill(session, prereq.skill_id)
                session.consecutive_failures = 0
                q = _fetch_question(
                    db, prereq.skill_id, session.current_grade, "easy", _served_ids(session)
                )
                if q:
                    _add_served(session, q.question_id)
                    db.commit()
                    return _question_to_schema(q, db, session)
        else:
            session.current_difficulty = new_difficulty
            engine_action = f"reduce_to_{new_difficulty}"

    # Check session completion
    if _check_session_complete(db, session):
        session.status = "completed"
        session.ended_at = datetime.utcnow()
        db.commit()
        return None

    # Fetch next question for current skill/grade/difficulty
    q = _fetch_question(
        db, session.current_skill_id, session.current_grade,
        session.current_difficulty, _served_ids(session)
    )

    if q is None:
        # No more questions for this skill — advance to next
        next_skill = _get_next_skill_in_grade(db, session)
        if next_skill is None:
            # Check if we have met the minimum questions
            if len(_served_ids(session)) < MIN_QUESTIONS:
                target_skill = _get_skill_for_review(db, session)
                if target_skill:
                    session.current_skill_id = target_skill.skill_id
                    session.current_difficulty = "medium"
                    q = _fetch_question(
                        db, target_skill.skill_id, session.current_grade,
                        "medium", _served_ids(session)
                    )
            if q is None:
                session.status = "completed"
                session.ended_at = datetime.utcnow()
                db.commit()
                return None
        session.current_skill_id = next_skill.skill_id
        session.current_difficulty = "medium"
        _add_visited_skill(session, next_skill.skill_id)
        q = _fetch_question(
            db, next_skill.skill_id, session.current_grade,
            "medium", _served_ids(session)
        )

    if q:
        _add_served(session, q.question_id)
        db.commit()
        return _question_to_schema(q, db, session)

    # Truly nothing left
    session.status = "completed"
    session.ended_at = datetime.utcnow()
    db.commit()
    return None
