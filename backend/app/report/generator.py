"""
Report Generator — aggregates session data into the full diagnostic report.

Computes:
  1. Skill Mastery Map (BKT P(L) per skill)
  2. Error Taxonomy Summary
  3. 5-Dimension Scores
  4. Grade-Equivalent Level
  5. Reading vs. Math Gap Diagnosis
  6. Foundational Gap Chain
  7. Personalised Narrative (templated)
"""

import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session as DBSession
from datetime import datetime

from app.models import (
    Session, Response, Question, BKTState, Skill,
    QuestionDimension, DimensionScore,
)
from app.engine.bkt import mastery_label


NCERT_CHAPTER_REFS = {
    "Arithmetic": "NCERT Mathematics — Chapter 1 (Numbers & Operations)",
    "Algebra": "NCERT Mathematics — Chapter 4 (Algebraic Expressions)",
    "Geometry": "NCERT Mathematics — Chapter 6 (Understanding Shapes)",
    "Statistics": "NCERT Mathematics — Chapter 14 (Data Handling)",
    "Probability": "NCERT Mathematics — Chapter 15 (Probability)",
}


def generate_report(db: DBSession, session_id: str) -> Dict[str, Any]:
    sess = db.query(Session).filter(Session.session_id == session_id).first()
    if not sess:
        return {}

    student = sess.student
    responses: List[Response] = sess.responses

    total_q = len(responses)
    correct_count = sum(1 for r in responses if r.is_correct)
    accuracy = round((correct_count / total_q * 100) if total_q > 0 else 0, 1)

    # -----------------------------------------------------------------------
    # 1. Skill Mastery Map
    # -----------------------------------------------------------------------
    skill_mastery = []
    bkt_states = db.query(BKTState).filter(BKTState.student_id == sess.student_id).all()
    for state in bkt_states:
        skill = db.query(Skill).filter(Skill.skill_id == state.skill_id).first()
        if skill:
            skill_mastery.append({
                "skill_id": state.skill_id,
                "skill_name": skill.skill_name,
                "grade_level": skill.grade_level or "",
                "topic_area": skill.topic_area or "",
                "p_mastery": round(state.p_mastery, 3),
                "attempts": state.attempts,
                "status": mastery_label(state.p_mastery),
            })
    skill_mastery.sort(key=lambda x: x["p_mastery"], reverse=True)

    # -----------------------------------------------------------------------
    # 2. Error Taxonomy Summary
    # -----------------------------------------------------------------------
    error_taxonomy: Dict[str, int] = {}
    for r in responses:
        if r.trap_type:
            error_taxonomy[r.trap_type] = error_taxonomy.get(r.trap_type, 0) + 1

    # -----------------------------------------------------------------------
    # 3. 5-Dimension Scores
    # -----------------------------------------------------------------------
    dim_names = ["dim_reading", "dim_understanding", "dim_application",
                 "dim_calculation", "dim_retention"]
    dim_totals = {d: 0 for d in dim_names}
    dim_correct = {d: 0 for d in dim_names}

    for r in responses:
        q = db.query(Question).filter(Question.question_id == r.question_id).first()
        if not q:
            continue
        dims = db.query(QuestionDimension).filter(
            QuestionDimension.question_id == r.question_id
        ).first()
        if not dims:
            continue
        for d in dim_names:
            if getattr(dims, d, False):
                dim_totals[d] += 1
                if r.is_correct:
                    dim_correct[d] += 1

    dimension_scores = {}
    for d in dim_names:
        key = d.replace("dim_", "")
        dimension_scores[key] = round(
            (dim_correct[d] / dim_totals[d] * 100) if dim_totals[d] > 0 else 0, 1
        )

    # Save dimension scores to DB
    existing_ds = sess.dimension_scores
    if existing_ds is None:
        existing_ds = DimensionScore(session_id=session_id)
        db.add(existing_ds)
    existing_ds.dim_reading = dimension_scores.get("reading", 0)
    existing_ds.dim_understanding = dimension_scores.get("understanding", 0)
    existing_ds.dim_application = dimension_scores.get("application", 0)
    existing_ds.dim_calculation = dimension_scores.get("calculation", 0)
    existing_ds.dim_retention = dimension_scores.get("retention", 0)
    db.flush()

    # -----------------------------------------------------------------------
    # 4. Grade-Equivalent Level
    # -----------------------------------------------------------------------
    grade_performance: Dict[int, List[bool]] = {}
    for r in responses:
        q = db.query(Question).filter(Question.question_id == r.question_id).first()
        if q and q.grade_level:
            grade_performance.setdefault(q.grade_level, []).append(r.is_correct)

    grade_equivalent = sess.selected_grade
    for grade in sorted(grade_performance.keys(), reverse=True):
        results = grade_performance[grade]
        if len(results) >= 3 and (sum(results) / len(results)) >= 0.70:
            grade_equivalent = grade
            break

    # -----------------------------------------------------------------------
    # 5. Reading vs. Math Gap
    # -----------------------------------------------------------------------
    reading_errors = sum(1 for r in responses if r.trap_type == "Reading_Error")
    word_problem_failures = sum(
        1 for r in responses
        if not r.is_correct and not r.twin_probe
    )
    reading_gap_pct = round(
        (reading_errors / word_problem_failures * 100) if word_problem_failures > 0 else 0, 1
    )
    reading_gap_detected = reading_gap_pct > 30

    # -----------------------------------------------------------------------
    # 6. Foundational Gap Chain
    # -----------------------------------------------------------------------
    gap_chain = []
    if sess.prerequisite_chain:
        try:
            raw_chain = json.loads(sess.prerequisite_chain)
            for item in raw_chain:
                from_skill = db.query(Skill).filter(
                    Skill.skill_id == item.get("from_skill")
                ).first()
                to_skill = db.query(Skill).filter(
                    Skill.skill_id == item.get("to_skill")
                ).first()
                gap_chain.append({
                    "from_skill": from_skill.skill_name if from_skill else item.get("from_skill"),
                    "from_grade": item.get("from_grade"),
                    "to_skill": to_skill.skill_name if to_skill else item.get("to_skill"),
                    "to_grade": item.get("to_grade"),
                    "reason": item.get("reason"),
                })
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # 7. Personalised Narrative
    # -----------------------------------------------------------------------
    narrative = _generate_narrative(
        student_name=student.name if student else "Student",
        grade=sess.selected_grade,
        grade_equivalent=grade_equivalent,
        accuracy=accuracy,
        dimension_scores=dimension_scores,
        error_taxonomy=error_taxonomy,
        reading_gap_detected=reading_gap_detected,
        reading_gap_pct=reading_gap_pct,
        gap_chain=gap_chain,
        skill_mastery=skill_mastery,
    )

    # -----------------------------------------------------------------------
    # Recommended Skills
    # -----------------------------------------------------------------------
    gaps = [s for s in skill_mastery if s["status"] == "Gap"]
    recommended = []
    for g in gaps[:3]:
        topic = g.get("topic_area", "General")
        recommended.append({
            "skill_id": g["skill_id"],
            "skill_name": g["skill_name"],
            "grade_level": g["grade_level"],
            "ncert_ref": NCERT_CHAPTER_REFS.get(topic, "NCERT Mathematics"),
        })

    return {
        "session_id": session_id,
        "student_name": student.name if student else "",
        "school": student.school if student else "",
        "selected_grade": sess.selected_grade,
        "grade_equivalent_level": grade_equivalent,
        "total_questions": total_q,
        "correct_answers": correct_count,
        "accuracy_pct": accuracy,
        "dimension_scores": dimension_scores,
        "skill_mastery": skill_mastery,
        "error_taxonomy": error_taxonomy,
        "reading_gap_detected": reading_gap_detected,
        "reading_gap_pct": reading_gap_pct,
        "foundational_gap_chain": gap_chain,
        "narrative": narrative,
        "recommended_skills": recommended,
        "started_at": sess.started_at.isoformat() if sess.started_at else None,
        "ended_at": sess.ended_at.isoformat() if sess.ended_at else None,
    }


def _generate_narrative(
    student_name: str,
    grade: int,
    grade_equivalent: int,
    accuracy: float,
    dimension_scores: Dict[str, float],
    error_taxonomy: Dict[str, int],
    reading_gap_detected: bool,
    reading_gap_pct: float,
    gap_chain: List[Dict],
    skill_mastery: List[Dict],
) -> str:
    parts = []

    # Opening performance statement
    if accuracy >= 80:
        parts.append(
            f"{student_name} demonstrated strong overall performance with {accuracy}% accuracy "
            f"on Grade {grade} content, performing at an equivalent Grade {grade_equivalent} level."
        )
    elif accuracy >= 55:
        parts.append(
            f"{student_name} showed developing competency with {accuracy}% accuracy "
            f"on Grade {grade} content, currently performing at a Grade {grade_equivalent} level."
        )
    else:
        parts.append(
            f"{student_name} requires targeted support — scoring {accuracy}% on Grade {grade} content "
            f"with performance equivalent to a Grade {grade_equivalent} level."
        )

    # Reading vs. Math gap
    calc = dimension_scores.get("calculation", 0)
    reading = dimension_scores.get("reading", 0)
    if reading_gap_detected:
        parts.append(
            f"The diagnostic identified a significant reading comprehension gap: "
            f"{student_name} successfully solved {calc:.0f}% of pure equations but only "
            f"{reading:.0f}% of word problems — suggesting a language barrier rather than a math deficit."
        )
    elif reading < 50 and calc > 60:
        parts.append(
            f"{student_name} shows stronger calculation skills ({calc:.0f}%) compared to "
            f"word problem performance ({reading:.0f}%), indicating some difficulty translating "
            f"language into mathematical operations."
        )

    # Primary error type
    if error_taxonomy:
        top_error = max(error_taxonomy, key=error_taxonomy.get)
        error_descriptions = {
            "Concept_Error": "conceptual misunderstandings (not just calculation errors)",
            "Calculation_Error": "calculation/arithmetic execution errors",
            "Careless_Slip": "careless slips (the underlying concepts appear understood)",
            "Sign_Error": "positive/negative sign confusion",
            "Procedural_Error": "procedural errors (correct concept, wrong steps)",
            "Reading_Error": "difficulties reading and interpreting question text",
        }
        desc = error_descriptions.get(top_error, top_error)
        parts.append(
            f"The most common error pattern was {desc}, "
            f"appearing in {error_taxonomy[top_error]} response(s)."
        )

    # Foundational gap chain
    if gap_chain:
        deepest = gap_chain[-1]
        parts.append(
            f"A foundational gap was traced back to {deepest['to_skill']} at Grade {deepest['to_grade']} — "
            f"strengthening this concept will directly improve performance in higher-grade topics."
        )

    # Recommendation
    mastered_count = sum(1 for s in skill_mastery if s["status"] == "Mastered")
    gap_count = sum(1 for s in skill_mastery if s["status"] == "Gap")
    if mastered_count > 0:
        parts.append(
            f"{student_name} has demonstrated mastery in {mastered_count} skill(s) "
            f"and should focus remediation on the {gap_count} identified gap area(s) below."
        )

    return " ".join(parts)
