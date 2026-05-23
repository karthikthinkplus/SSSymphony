"""
Pydantic schemas for request/response validation.
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr


# ---------------------------------------------------------------------------
# Session schemas
# ---------------------------------------------------------------------------
class SessionStartRequest(BaseModel):
    name: str
    school: Optional[str] = ""
    grade: int   # 5-10


class QuestionOut(BaseModel):
    question_id: str
    question_text: str
    question_type: str
    word_problem_flag: bool
    grade_level: int
    difficulty_band: str
    skill_name: str
    topic_area: str
    option_a: Optional[str]
    option_b: Optional[str]
    option_c: Optional[str]
    option_d: Optional[str]
    question_number: int
    is_twin_probe: bool = False


class SessionStartResponse(BaseModel):
    session_id: str
    student_id: str
    first_question: QuestionOut


class RespondRequest(BaseModel):
    session_id: str
    question_id: str
    selected_option: str        # A | B | C | D
    response_time_ms: Optional[int] = None


class RespondResponse(BaseModel):
    is_correct: bool
    session_complete: bool
    next_question: Optional[QuestionOut] = None
    bkt_update: Optional[Dict[str, float]] = None
    engine_action: Optional[str] = None   # for transparency


# ---------------------------------------------------------------------------
# Report schemas
# ---------------------------------------------------------------------------
class SkillMasteryItem(BaseModel):
    skill_id: str
    skill_name: str
    grade_level: str
    topic_area: str
    p_mastery: float
    attempts: int
    status: str   # Mastered | Developing | Gap


class DimensionScores(BaseModel):
    reading: float
    understanding: float
    application: float
    calculation: float
    retention: float


class GapChainItem(BaseModel):
    from_skill: str
    from_grade: int
    to_skill: str
    to_grade: int
    reason: str


class ReportOut(BaseModel):
    session_id: str
    student_name: str
    school: str
    selected_grade: int
    grade_equivalent_level: int
    total_questions: int
    correct_answers: int
    accuracy_pct: float
    dimension_scores: DimensionScores
    skill_mastery: List[SkillMasteryItem]
    error_taxonomy: Dict[str, int]
    reading_gap_detected: bool
    reading_gap_pct: float
    foundational_gap_chain: List[GapChainItem]
    narrative: str
    recommended_skills: List[Dict[str, Any]]
    started_at: str
    ended_at: Optional[str]


# ---------------------------------------------------------------------------
# Admin schemas
# ---------------------------------------------------------------------------
class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class ImportResultResponse(BaseModel):
    success: bool
    skills_imported: int
    questions_imported: int
    traps_imported: int
    dimensions_imported: int
    q_matrix_rows: int
    errors: List[str]
    warnings: List[str]


class StudentListItem(BaseModel):
    student_id: str
    name: str
    school: str
    class_grade: int
    last_session_date: Optional[str]
    overall_score: Optional[float]
    sessions_count: int


class DashboardStats(BaseModel):
    total_students: int
    total_sessions: int
    sessions_this_week: int
    avg_score_by_grade: Dict[str, float]
    top_failing_skills: List[Dict[str, Any]]
    trap_type_distribution: Dict[str, int]


class CohortAnalytics(BaseModel):
    grade: int
    skill_failure_rates: List[Dict[str, Any]]
    trap_type_counts: Dict[str, int]
    avg_theta: float
    prerequisite_gaps: List[Dict[str, Any]]


class SessionReplayItem(BaseModel):
    step: int
    question_id: str
    question_text: str
    skill_name: str
    grade: int
    difficulty: str
    selected_option: str
    is_correct: bool
    trap_type: Optional[str]
    engine_action: str
    theta_before: float
    theta_after: float
    bkt_before: float
    bkt_after: float
    responded_at: str


class QuestionBankItem(BaseModel):
    question_id: str
    question_text: str
    question_type: str
    word_problem_flag: bool
    primary_skill_id: str
    skill_name: str
    grade_level: int
    difficulty_band: str
    correct_option: str
    has_twin: bool
    has_traps: bool
