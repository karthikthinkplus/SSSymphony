"""
Admin Router — protected admin/teacher endpoints.

POST /api/admin/login
POST /api/admin/import
GET  /api/admin/dashboard
GET  /api/admin/students
GET  /api/admin/student/{student_id}/report
GET  /api/admin/cohort/{grade}
GET  /api/admin/session/{session_id}/replay
GET  /api/admin/questions
"""

import os
import tempfile
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session as DBSession
from jose import JWTError, jwt
import hashlib

from app.database import get_db
from app.models import (
    AdminUser, Student, Session, Response, Question, Skill,
    BKTState, AnswerTrap,
)
from app.schemas import (
    AdminLoginRequest, AdminLoginResponse, ImportResultResponse,
)
from app.importer.excel_parser import import_excel
from app.report.generator import generate_report

router = APIRouter(prefix="/api/admin", tags=["admin"])

SECRET_KEY = os.getenv("JWT_SECRET", "symphony-adaptive-math-secret-key-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/login")


def verify_password(plain: str, hashed: str) -> bool:
    return hashlib.sha256(plain.encode()).hexdigest() == hashed


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_admin(token: str = Depends(oauth2_scheme), db: DBSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(AdminUser).filter(AdminUser.username == username).first()
    if user is None:
        raise credentials_exception
    return user


@router.post("/login", response_model=AdminLoginResponse)
def login(req: AdminLoginRequest, db: DBSession = Depends(get_db)):
    user = db.query(AdminUser).filter(AdminUser.username == req.username).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.username, "role": user.role})
    return AdminLoginResponse(access_token=token, role=user.role)


@router.post("/import", response_model=ImportResultResponse)
async def import_question_bank(
    file: UploadFile = File(...),
    db: DBSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx/.xls) are accepted")

    # Save to temp file
    suffix = ".xlsx" if file.filename.endswith(".xlsx") else ".xls"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    result = import_excel(tmp_path, db)
    os.unlink(tmp_path)
    return ImportResultResponse(**result)


@router.get("/dashboard")
def get_dashboard(db: DBSession = Depends(get_db), current_admin: AdminUser = Depends(get_current_admin)):
    total_students = db.query(Student).count()
    total_sessions = db.query(Session).count()
    week_ago = datetime.utcnow() - timedelta(days=7)
    sessions_this_week = db.query(Session).filter(Session.started_at >= week_ago).count()

    # Average accuracy by grade
    grades = range(5, 11)
    avg_score_by_grade = {}
    for g in grades:
        students_in_grade = db.query(Student).filter(Student.class_grade == g).all()
        if not students_in_grade:
            continue
        sids = [s.student_id for s in students_in_grade]
        sessions_g = db.query(Session).filter(
            Session.student_id.in_(sids),
            Session.status == "completed"
        ).all()
        if not sessions_g:
            continue
        accuracies = []
        for sess in sessions_g:
            resps = sess.responses
            if resps:
                acc = sum(1 for r in resps if r.is_correct) / len(resps) * 100
                accuracies.append(acc)
        if accuracies:
            avg_score_by_grade[str(g)] = round(sum(accuracies) / len(accuracies), 1)

    # Top failing skills (by BKT gap)
    gap_states = (
        db.query(BKTState)
        .filter(BKTState.p_mastery <= 0.30)
        .all()
    )
    skill_gap_counts: dict = {}
    for state in gap_states:
        skill_gap_counts[state.skill_id] = skill_gap_counts.get(state.skill_id, 0) + 1

    top_failing = []
    for sid, count in sorted(skill_gap_counts.items(), key=lambda x: -x[1])[:10]:
        skill = db.query(Skill).filter(Skill.skill_id == sid).first()
        top_failing.append({
            "skill_id": sid,
            "skill_name": skill.skill_name if skill else sid,
            "grade_level": skill.grade_level if skill else "",
            "gap_count": count,
        })

    # Trap type distribution
    trap_counts = {}
    for r in db.query(Response).filter(Response.trap_type.isnot(None)).all():
        trap_counts[r.trap_type] = trap_counts.get(r.trap_type, 0) + 1

    return {
        "total_students": total_students,
        "total_sessions": total_sessions,
        "sessions_this_week": sessions_this_week,
        "avg_score_by_grade": avg_score_by_grade,
        "top_failing_skills": top_failing,
        "trap_type_distribution": trap_counts,
    }


@router.get("/students")
def get_students(
    search: Optional[str] = None,
    grade: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: DBSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    q = db.query(Student)
    if search:
        q = q.filter(Student.name.ilike(f"%{search}%"))
    if grade:
        q = q.filter(Student.class_grade == grade)
    students = q.offset(skip).limit(limit).all()

    result = []
    for s in students:
        sessions = db.query(Session).filter(Session.student_id == s.student_id).all()
        last_session = None
        overall_score = None
        if sessions:
            completed = [sess for sess in sessions if sess.status == "completed"]
            if completed:
                latest = max(completed, key=lambda x: x.started_at)
                last_session = latest.started_at.isoformat()
                resps = latest.responses
                if resps:
                    overall_score = round(
                        sum(1 for r in resps if r.is_correct) / len(resps) * 100, 1
                    )
        result.append({
            "student_id": s.student_id,
            "name": s.name,
            "school": s.school,
            "class_grade": s.class_grade,
            "last_session_date": last_session,
            "overall_score": overall_score,
            "sessions_count": len(sessions),
        })
    return {"students": result, "total": q.count()}


@router.get("/student/{student_id}/report")
def get_student_report(
    student_id: str,
    db: DBSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    sessions = (
        db.query(Session)
        .filter(Session.student_id == student_id, Session.status == "completed")
        .order_by(Session.started_at.desc())
        .first()
    )
    if not sessions:
        raise HTTPException(status_code=404, detail="No completed sessions for this student")
    return generate_report(db, sessions.session_id)


@router.get("/cohort/{grade}")
def get_cohort_analytics(
    grade: int,
    db: DBSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    students = db.query(Student).filter(Student.class_grade == grade).all()
    if not students:
        return {"grade": grade, "skill_failure_rates": [], "trap_type_counts": {}, "avg_theta": 0.0, "prerequisite_gaps": []}

    sids = [s.student_id for s in students]
    sessions = db.query(Session).filter(Session.student_id.in_(sids)).all()

    # Trap type distribution for this grade
    trap_counts = {}
    all_responses = []
    thetas = []
    for sess in sessions:
        thetas.append(sess.current_theta or 0.0)
        for r in sess.responses:
            all_responses.append(r)
            if r.trap_type:
                trap_counts[r.trap_type] = trap_counts.get(r.trap_type, 0) + 1

    # Skill failure rates
    skill_failures: dict = {}
    skill_totals: dict = {}
    for r in all_responses:
        q = db.query(Question).filter(Question.question_id == r.question_id).first()
        if q and q.primary_skill_id:
            skill_totals[q.primary_skill_id] = skill_totals.get(q.primary_skill_id, 0) + 1
            if not r.is_correct:
                skill_failures[q.primary_skill_id] = skill_failures.get(q.primary_skill_id, 0) + 1

    skill_failure_rates = []
    for sid, total in skill_totals.items():
        fail = skill_failures.get(sid, 0)
        skill = db.query(Skill).filter(Skill.skill_id == sid).first()
        skill_failure_rates.append({
            "skill_id": sid,
            "skill_name": skill.skill_name if skill else sid,
            "failure_rate": round(fail / total * 100, 1) if total > 0 else 0,
            "total_attempts": total,
        })
    skill_failure_rates.sort(key=lambda x: -x["failure_rate"])

    # Prerequisite gaps
    prereq_gaps = []
    gap_counts: dict = {}
    for sess in sessions:
        import json as _json
        if sess.prerequisite_chain:
            try:
                chain = _json.loads(sess.prerequisite_chain)
                for item in chain:
                    to_skill = item.get("to_skill", "")
                    gap_counts[to_skill] = gap_counts.get(to_skill, 0) + 1
            except Exception:
                pass
    for skill_id, count in sorted(gap_counts.items(), key=lambda x: -x[1])[:5]:
        skill = db.query(Skill).filter(Skill.skill_id == skill_id).first()
        prereq_gaps.append({
            "skill_id": skill_id,
            "skill_name": skill.skill_name if skill else skill_id,
            "grade_level": skill.grade_level if skill else "",
            "occurrence_count": count,
        })

    return {
        "grade": grade,
        "student_count": len(students),
        "skill_failure_rates": skill_failure_rates[:15],
        "trap_type_counts": trap_counts,
        "avg_theta": round(sum(thetas) / len(thetas), 3) if thetas else 0.0,
        "prerequisite_gaps": prereq_gaps,
    }


@router.get("/session/{session_id}/replay")
def get_session_replay(
    session_id: str,
    db: DBSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    session = db.query(Session).filter(Session.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    responses = db.query(Response).filter(
        Response.session_id == session_id
    ).order_by(Response.responded_at).all()

    replay = []
    theta = 0.0
    bkt: dict = {}

    for i, r in enumerate(responses):
        q = db.query(Question).filter(Question.question_id == r.question_id).first()
        skill = db.query(Skill).filter(
            Skill.skill_id == (q.primary_skill_id if q else None)
        ).first() if q else None

        theta_before = theta
        from app.engine.irt import update_theta_mle
        from app.engine.bkt import bkt_update
        bkt_before = bkt.get(q.primary_skill_id if q else "", 0.10)
        bkt_after_val = bkt_update(bkt_before, r.is_correct)
        if q and q.primary_skill_id:
            bkt[q.primary_skill_id] = bkt_after_val
        if q:
            theta = update_theta_mle(theta, r.is_correct, q.difficulty_band or "medium")

        replay.append({
            "step": i + 1,
            "question_id": r.question_id,
            "question_text": (q.question_text[:120] + "…") if q and len(q.question_text) > 120 else (q.question_text if q else ""),
            "skill_name": skill.skill_name if skill else "",
            "grade": q.grade_level if q else 0,
            "difficulty": q.difficulty_band if q else "",
            "selected_option": r.selected_option or "",
            "is_correct": r.is_correct,
            "trap_type": r.trap_type,
            "engine_action": "twin_probe" if r.twin_probe else ("remediation" if r.trap_type else "standard"),
            "theta_before": round(theta_before, 3),
            "theta_after": round(theta, 3),
            "bkt_before": round(bkt_before, 3),
            "bkt_after": round(bkt_after_val, 3),
            "responded_at": r.responded_at.isoformat() if r.responded_at else "",
        })

    return {"session_id": session_id, "replay": replay}


@router.get("/questions")
def get_questions(
    grade: Optional[int] = None,
    difficulty: Optional[str] = None,
    skill_id: Optional[str] = None,
    word_problem: Optional[bool] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: DBSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    q = db.query(Question)
    if grade:
        q = q.filter(Question.grade_level == grade)
    if difficulty:
        q = q.filter(Question.difficulty_band == difficulty)
    if skill_id:
        q = q.filter(Question.primary_skill_id == skill_id)
    if word_problem is not None:
        q = q.filter(Question.word_problem_flag == word_problem)
    if search:
        q = q.filter(Question.question_text.ilike(f"%{search}%"))

    total = q.count()
    questions = q.offset(skip).limit(limit).all()

    result = []
    for quest in questions:
        skill = db.query(Skill).filter(Skill.skill_id == quest.primary_skill_id).first()
        trap_count = db.query(AnswerTrap).filter(AnswerTrap.question_id == quest.question_id).count()
        result.append({
            "question_id": quest.question_id,
            "question_text": quest.question_text[:100] + "…" if len(quest.question_text) > 100 else quest.question_text,
            "question_type": quest.question_type,
            "word_problem_flag": quest.word_problem_flag,
            "primary_skill_id": quest.primary_skill_id,
            "skill_name": skill.skill_name if skill else "",
            "grade_level": quest.grade_level,
            "difficulty_band": quest.difficulty_band,
            "correct_option": quest.correct_option,
            "has_twin": bool(quest.equation_twin_id),
            "has_traps": trap_count > 0,
        })
    return {"questions": result, "total": total}
