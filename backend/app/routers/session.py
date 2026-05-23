"""
Session Router — Student-facing endpoints.

POST /api/session/start   → create student + session, return first question
POST /api/session/respond → record response, run orchestrator, return next question
GET  /api/session/report/{session_id} → return full diagnostic report
GET  /api/session/{session_id}/status → check if session is in_progress or completed
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models import Student, Session, Response, Question
from app.schemas import (
    SessionStartRequest, SessionStartResponse,
    RespondRequest, RespondResponse,
    QuestionOut,
)
from app.engine.orchestrator import get_next_question
from app.report.generator import generate_report

router = APIRouter(prefix="/api/session", tags=["session"])


def _make_student(db: DBSession, name: str, school: str, grade: int) -> Student:
    student = Student(
        name=name,
        school=school,
        class_grade=grade,
    )
    db.add(student)
    db.flush()
    return student


@router.post("/start", response_model=SessionStartResponse)
def start_session(req: SessionStartRequest, db: DBSession = Depends(get_db)):
    if req.grade not in range(5, 11):
        raise HTTPException(status_code=400, detail="Grade must be between 5 and 10")

    student = _make_student(db, req.name, req.school or "", req.grade)

    session = Session(
        student_id=student.student_id,
        selected_grade=req.grade,
        current_grade=req.grade,
        current_difficulty="medium",
        current_theta=0.0,
        consecutive_failures=0,
        consecutive_correct=0,
        status="in_progress",
    )
    db.add(session)
    db.flush()

    # Get first question via orchestrator
    first_q = get_next_question(db, session, last_response=None)
    if first_q is None:
        raise HTTPException(status_code=404, detail="No questions available for this grade")

    db.commit()
    return SessionStartResponse(
        session_id=session.session_id,
        student_id=student.student_id,
        first_question=first_q,
    )


@router.post("/respond", response_model=RespondResponse)
def submit_response(req: RespondRequest, db: DBSession = Depends(get_db)):
    session = db.query(Session).filter(Session.session_id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == "completed":
        raise HTTPException(status_code=400, detail="Session already completed")

    q = db.query(Question).filter(Question.question_id == req.question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    # Check correctness
    is_correct = q.correct_option.upper() == req.selected_option.upper()

    # Determine if this is a twin probe
    is_twin = session.twin_probe_pending and (
        session.twin_origin_question_id is not None
        and req.question_id != session.twin_origin_question_id
    )

    # Record response
    resp = Response(
        session_id=req.session_id,
        question_id=req.question_id,
        selected_option=req.selected_option.upper(),
        is_correct=is_correct,
        twin_probe=is_twin,
        response_time_ms=req.response_time_ms,
        responded_at=datetime.utcnow(),
    )
    db.add(resp)
    db.flush()

    # Get BKT state before update (for return)
    from app.models import BKTState
    bkt_before = {}
    if session.current_skill_id:
        state = db.query(BKTState).filter(
            BKTState.student_id == session.student_id,
            BKTState.skill_id == session.current_skill_id,
        ).first()
        if state:
            bkt_before[session.current_skill_id] = state.p_mastery

    # Run orchestrator to get next question
    next_q = get_next_question(db, session, last_response=resp)

    # Get BKT state after update
    bkt_after = {}
    if session.current_skill_id:
        state = db.query(BKTState).filter(
            BKTState.student_id == session.student_id,
            BKTState.skill_id == session.current_skill_id,
        ).first()
        if state:
            bkt_after[session.current_skill_id] = round(state.p_mastery, 3)

    session_complete = (session.status == "completed") or (next_q is None)

    db.commit()
    return RespondResponse(
        is_correct=is_correct,
        session_complete=session_complete,
        next_question=next_q,
        bkt_update=bkt_after,
        engine_action="orchestrator_ran",
    )


@router.get("/report/{session_id}")
def get_report(session_id: str, db: DBSession = Depends(get_db)):
    session = db.query(Session).filter(Session.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return generate_report(db, session_id)


@router.get("/{session_id}/status")
def get_status(session_id: str, db: DBSession = Depends(get_db)):
    session = db.query(Session).filter(Session.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    served = [x for x in (session.questions_served or "").split(",") if x]
    return {
        "session_id": session_id,
        "status": session.status,
        "questions_served": len(served),
        "current_skill_id": session.current_skill_id,
        "current_grade": session.current_grade,
        "current_difficulty": session.current_difficulty,
        "theta": session.current_theta,
    }
