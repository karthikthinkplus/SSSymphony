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
    
    # Difficulty Weights (IRT proxy)
    DIFFICULTY_WEIGHTS = {
        "easy": 0.7,
        "medium": 1.0,
        "hard": 1.3
    }
    
    # Accumulators for weighted score credit and total weighted question occurrences
    weighted_credit = {d: 0.0 for d in dim_names}
    weighted_total = {d: 0.0 for d in dim_names}

    for r in responses:
        q = db.query(Question).filter(Question.question_id == r.question_id).first()
        if not q:
            continue
        dims = db.query(QuestionDimension).filter(
            QuestionDimension.question_id == r.question_id
        ).first()
        if not dims:
            continue

        # Get the difficulty weight for the question (default to 1.0 if invalid)
        diff_band = (q.difficulty_band or "medium").lower()
        w_i = DIFFICULTY_WEIGHTS.get(diff_band, 1.0)

        # Retrieve the trap type if incorrect
        trap_type = r.trap_type

        for d in dim_names:
            if getattr(dims, d, False):
                weighted_total[d] += w_i
                
                if r.is_correct:
                    # Full credit on correct answers
                    weighted_credit[d] += 1.0 * w_i
                else:
                    # Partial / full credit allocation based on CDM error-trap attribution
                    credit = 0.0
                    if trap_type == "Reading_Error":
                        if d == "dim_reading":
                            credit = 0.0
                        elif d in ["dim_understanding", "dim_calculation"]:
                            credit = 1.0  # Perfect credit since math concepts and math logic are clean
                        elif d in ["dim_application", "dim_retention"]:
                            credit = 0.8  # Strong partial credit
                    elif trap_type in ["Calculation_Error", "Sign_Error"]:
                        if d == "dim_calculation":
                            credit = 0.0
                        elif d in ["dim_reading", "dim_understanding"]:
                            credit = 1.0  # Perfect credit since understanding and reading are clean
                        elif d in ["dim_application", "dim_retention"]:
                            credit = 0.8  # Strong partial credit
                    elif trap_type in ["Concept_Error", "Procedural_Error"]:
                        if d in ["dim_understanding", "dim_application"]:
                            credit = 0.0
                        elif d in ["dim_reading", "dim_calculation", "dim_retention"]:
                            credit = 0.8  # Strong partial credit (concept error doesn't fully deny these)
                    elif trap_type == "Careless_Slip":
                        if d == "dim_calculation":
                            credit = 0.5  # execution slip
                        else:
                            credit = 0.9  # high credit as they know the concepts
                    else:
                        credit = 0.0  # fallback for other/unclassified errors

                    weighted_credit[d] += credit * w_i

    # Bayesian Shrinkage (Laplace smoothing)
    # We use a virtual prior weight of 2.0 (equivalent to two medium questions)
    # centered on the student's overall test accuracy (or 60% if no questions attempted)
    w_prior = 2.0
    prior_score_pct = accuracy if total_q > 0 else 60.0
    prior_fraction = prior_score_pct / 100.0

    dimension_scores = {}
    for d in dim_names:
        key = d.replace("dim_", "")
        # Apply formula: (Sum(Credit * W) + W_prior * Prior) / (Sum(W) + W_prior) * 100
        numerator = weighted_credit[d] + (w_prior * prior_fraction)
        denominator = weighted_total[d] + w_prior
        dimension_scores[key] = round((numerator / denominator) * 100.0, 1)

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
    # 6b. Behavioral Insights & Comprehension Error Detection
    # -----------------------------------------------------------------------
    # Under 3 seconds (3000 ms) response time is flagged as rapid guessing
    guessed_count = sum(1 for r in responses if r.response_time_ms is not None and r.response_time_ms < 3000)
    guessed_pct = round((guessed_count / total_q * 100) if total_q > 0 else 0, 1)

    # Comprehension error occurs if they fail word problem but solve twin, or if Reading_Error is marked
    comprehension_error_count = sum(1 for r in responses if (r.twin_probe and r.is_correct) or r.trap_type == "Reading_Error")
    comprehension_error_detected = comprehension_error_count > 0

    # -----------------------------------------------------------------------
    # 6c. Detailed Timing & Speed Diagnostics
    # -----------------------------------------------------------------------
    response_timeline = []
    total_time_ms = 0
    valid_times_count = 0
    slowest_q = None
    fastest_q = None
    
    pace_breakdown = {"rushed": 0, "optimal": 0, "deliberate": 0}
    
    for idx, r in enumerate(responses):
        q = db.query(Question).filter(Question.question_id == r.question_id).first()
        skill_name = "Unknown Skill"
        if q:
            skill = db.query(Skill).filter(Skill.skill_id == q.primary_skill_id).first()
            if skill:
                skill_name = skill.skill_name
                
        t_ms = r.response_time_ms or 0
        total_time_ms += t_ms
        if t_ms > 0:
            valid_times_count += 1
            
        time_sec = round(t_ms / 1000.0, 1)
        
        # Categorize pacing: Rushed (< 3s), Optimal (3s to 45s), Deliberate (> 45s)
        if t_ms < 3000:
            pace_category = "Rushed"
            pace_breakdown["rushed"] += 1
        elif t_ms <= 45000:
            pace_category = "Optimal"
            pace_breakdown["optimal"] += 1
        else:
            pace_category = "Deliberate"
            pace_breakdown["deliberate"] += 1
            
        response_timeline.append({
            "question_number": idx + 1,
            "skill_name": skill_name,
            "time_sec": time_sec,
            "is_correct": r.is_correct,
            "pace_category": pace_category,
        })
        
        if t_ms > 0:
            if slowest_q is None or t_ms > slowest_q["time_ms"]:
                slowest_q = {
                    "question_number": idx + 1,
                    "time_ms": t_ms,
                    "time_sec": time_sec,
                    "skill_name": skill_name
                }
            if fastest_q is None or t_ms < fastest_q["time_ms"]:
                fastest_q = {
                    "question_number": idx + 1,
                    "time_ms": t_ms,
                    "time_sec": time_sec,
                    "skill_name": skill_name
                }
                
    avg_response_time_sec = round((total_time_ms / valid_times_count / 1000.0) if valid_times_count > 0 else 0, 1)
    total_duration_sec = round(total_time_ms / 1000.0, 1)

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
        guessed_count=guessed_count,
        guessed_pct=guessed_pct,
        comprehension_error_count=comprehension_error_count,
        comprehension_error_detected=comprehension_error_detected,
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
        "guessed_count": guessed_count,
        "guessed_pct": guessed_pct,
        "comprehension_error_count": comprehension_error_count,
        "comprehension_error_detected": comprehension_error_detected,
        "avg_response_time_sec": avg_response_time_sec,
        "total_duration_sec": total_duration_sec,
        "slowest_question": slowest_q,
        "fastest_question": fastest_q,
        "response_timeline": response_timeline,
        "pace_breakdown": pace_breakdown,
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
    guessed_count: int,
    guessed_pct: float,
    comprehension_error_count: int,
    comprehension_error_detected: bool,
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

    # Behavioral and Comprehension insights based on response time and twin probes
    behavioral_insights = []
    if guessed_count > 0:
        behavioral_insights.append(
            f"In terms of test-taking behavior, {student_name} was flagged for rapid guessing on {guessed_count} question(s) "
            f"({guessed_pct:.1f}% of total responses), where answers were submitted in under 3 seconds. This suggest they "
            f"likely guessed these questions without thoroughly reading the prompts."
        )
    else:
        behavioral_insights.append(
            f"Analysis of pacing indicates that {student_name} demonstrated thoughtful, deliberate decision-making, with "
            f"no responses flagged as rapid guesses (under 3 seconds)."
        )

    if comprehension_error_detected:
        behavioral_insights.append(
            f"Additionally, the engine successfully isolated {comprehension_error_count} instances where "
            f"{student_name} made a reading/comprehension error. In these cases, the student failed the word problem "
            f"format but successfully solved the mathematical equation twin. This clearly defines a language comprehension "
            f"error rather than a mathematical core deficit."
        )
    else:
        behavioral_insights.append(
            f"Furthermore, there were no verified comprehension errors where the student failed a word problem "
            f"but solved its identical equation twin, suggesting consistent decoding across verbal and symbol formats."
        )

    parts.append(" ".join(behavioral_insights))

    return " ".join(parts)
