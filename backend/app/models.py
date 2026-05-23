"""
SQLAlchemy ORM models — all 9 tables from the master prompt schema.
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


def new_uuid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Sheet 1 — Skills (Knowledge Graph nodes)
# ---------------------------------------------------------------------------
class Skill(Base):
    __tablename__ = "skills"

    skill_id = Column(String(20), primary_key=True)
    skill_name = Column(String(200), nullable=False)
    grade_level = Column(String(10))
    topic_area = Column(String(100))
    difficulty_band = Column(String(20))
    prerequisite_skill_ids = Column(Text)   # comma-separated; parsed into knowledge_graph
    notes = Column(Text)

    # relationships
    questions = relationship("Question", back_populates="primary_skill",
                              foreign_keys="Question.primary_skill_id")
    prerequisite_of = relationship(
        "KnowledgeGraph", foreign_keys="KnowledgeGraph.child_skill_id",
        back_populates="child_skill"
    )
    prerequisites = relationship(
        "KnowledgeGraph", foreign_keys="KnowledgeGraph.parent_skill_id",
        back_populates="parent_skill"
    )


# ---------------------------------------------------------------------------
# Knowledge Graph (parsed prerequisite edges)
# ---------------------------------------------------------------------------
class KnowledgeGraph(Base):
    __tablename__ = "knowledge_graph"

    child_skill_id = Column(String(20), ForeignKey("skills.skill_id"), primary_key=True)
    parent_skill_id = Column(String(20), ForeignKey("skills.skill_id"), primary_key=True)

    child_skill = relationship("Skill", foreign_keys=[child_skill_id],
                               back_populates="prerequisite_of")
    parent_skill = relationship("Skill", foreign_keys=[parent_skill_id],
                                back_populates="prerequisites")


# ---------------------------------------------------------------------------
# Sheet 2 — Questions
# ---------------------------------------------------------------------------
class Question(Base):
    __tablename__ = "questions"

    question_id = Column(String(100), primary_key=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(30))
    word_problem_flag = Column(Boolean, default=False)
    equation_twin_id = Column(String(100), ForeignKey("questions.question_id"), nullable=True)
    primary_skill_id = Column(String(20), ForeignKey("skills.skill_id"))
    secondary_skill_ids = Column(Text)
    grade_level = Column(Integer)
    difficulty_band = Column(String(20))
    option_a = Column(Text)
    option_b = Column(Text)
    option_c = Column(Text)
    option_d = Column(Text)
    correct_option = Column(String(1))

    primary_skill = relationship("Skill", back_populates="questions",
                                 foreign_keys=[primary_skill_id])
    twin = relationship("Question", remote_side="Question.question_id",
                        foreign_keys=[equation_twin_id])
    q_matrix_entries = relationship("QMatrix", back_populates="question",
                                    cascade="all, delete-orphan")
    answer_traps = relationship("AnswerTrap", back_populates="question",
                                cascade="all, delete-orphan")
    dimensions = relationship("QuestionDimension", back_populates="question",
                              uselist=False, cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Sheet 3 — Q-Matrix
# ---------------------------------------------------------------------------
class QMatrix(Base):
    __tablename__ = "q_matrix"

    question_id = Column(String(100), ForeignKey("questions.question_id"), primary_key=True)
    skill_id = Column(String(20), ForeignKey("skills.skill_id"), primary_key=True)

    question = relationship("Question", back_populates="q_matrix_entries")
    skill = relationship("Skill")


# ---------------------------------------------------------------------------
# Sheet 4 — Answer Traps (Distractors + CDM diagnostics)
# ---------------------------------------------------------------------------
class AnswerTrap(Base):
    __tablename__ = "answer_traps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(String(100), ForeignKey("questions.question_id"))
    option_label = Column(String(1))
    option_text = Column(Text)
    trap_type = Column(String(50))          # Calculation_Error, Concept_Error, …
    skill_gap_id = Column(String(20), ForeignKey("skills.skill_id"), nullable=True)
    misconception = Column(String(200))
    misconception_detail = Column(Text)
    remedial_action = Column(String(50))    # serve_same_level | go_down_grade | …
    remedial_skill_id = Column(String(20), ForeignKey("skills.skill_id"), nullable=True)
    remedial_grade = Column(Integer, nullable=True)

    question = relationship("Question", back_populates="answer_traps")
    skill_gap = relationship("Skill", foreign_keys=[skill_gap_id])
    remedial_skill = relationship("Skill", foreign_keys=[remedial_skill_id])


# ---------------------------------------------------------------------------
# Sheet 5 — Question Dimensions
# ---------------------------------------------------------------------------
class QuestionDimension(Base):
    __tablename__ = "question_dimensions"

    question_id = Column(String(100), ForeignKey("questions.question_id"), primary_key=True)
    dim_reading = Column(Boolean, default=False)
    dim_understanding = Column(Boolean, default=False)
    dim_application = Column(Boolean, default=False)
    dim_calculation = Column(Boolean, default=False)
    dim_retention = Column(Boolean, default=False)
    primary_dimension = Column(String(30))
    word_eq_pair_id = Column(String(100), nullable=True)

    question = relationship("Question", back_populates="dimensions")


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------
class Student(Base):
    __tablename__ = "students"

    student_id = Column(String(36), primary_key=True, default=new_uuid)
    name = Column(String(200))
    email = Column(String(200), unique=True, nullable=True)
    school = Column(String(200))
    class_grade = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("Session", back_populates="student")
    bkt_states = relationship("BKTState", back_populates="student")


# ---------------------------------------------------------------------------
# Assessment Sessions
# ---------------------------------------------------------------------------
class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(String(36), primary_key=True, default=new_uuid)
    student_id = Column(String(36), ForeignKey("students.student_id"))
    selected_grade = Column(Integer)
    current_theta = Column(Float, default=0.0)
    current_skill_id = Column(String(20), ForeignKey("skills.skill_id"), nullable=True)
    current_grade = Column(Integer)
    current_difficulty = Column(String(20), default="medium")
    consecutive_failures = Column(Integer, default=0)
    consecutive_correct = Column(Integer, default=0)
    status = Column(String(20), default="in_progress")   # in_progress | completed
    twin_probe_pending = Column(Boolean, default=False)
    twin_origin_question_id = Column(String(100), nullable=True)
    pending_confirmation = Column(Boolean, default=False)
    questions_served = Column(Text, default="")          # comma-separated question_ids
    skills_visited = Column(Text, default="")            # comma-separated skill_ids
    prerequisite_chain = Column(Text, default="")        # JSON traversal log
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    student = relationship("Student", back_populates="sessions")
    responses = relationship("Response", back_populates="session",
                             cascade="all, delete-orphan")
    dimension_scores = relationship("DimensionScore", back_populates="session",
                                    uselist=False, cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------
class Response(Base):
    __tablename__ = "responses"

    response_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.session_id"))
    question_id = Column(String(100), ForeignKey("questions.question_id"))
    selected_option = Column(String(1))
    is_correct = Column(Boolean)
    trap_type = Column(String(50), nullable=True)
    skill_gap_id = Column(String(20), nullable=True)
    misconception = Column(String(200), nullable=True)
    twin_probe = Column(Boolean, default=False)
    response_time_ms = Column(Integer, nullable=True)
    responded_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="responses")
    question = relationship("Question")


# ---------------------------------------------------------------------------
# BKT State (per student per skill)
# ---------------------------------------------------------------------------
class BKTState(Base):
    __tablename__ = "bkt_state"

    student_id = Column(String(36), ForeignKey("students.student_id"), primary_key=True)
    skill_id = Column(String(20), ForeignKey("skills.skill_id"), primary_key=True)
    p_mastery = Column(Float, default=0.10)
    attempts = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="bkt_states")
    skill = relationship("Skill")


# ---------------------------------------------------------------------------
# Dimension Scores (aggregated per session)
# ---------------------------------------------------------------------------
class DimensionScore(Base):
    __tablename__ = "dimension_scores"

    session_id = Column(String(36), ForeignKey("sessions.session_id"), primary_key=True)
    dim_reading = Column(Float, default=0.0)
    dim_understanding = Column(Float, default=0.0)
    dim_application = Column(Float, default=0.0)
    dim_calculation = Column(Float, default=0.0)
    dim_retention = Column(Float, default=0.0)

    session = relationship("Session", back_populates="dimension_scores")


# ---------------------------------------------------------------------------
# Admin Users
# ---------------------------------------------------------------------------
class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    role = Column(String(20), default="teacher")   # admin | teacher | viewer
    created_at = Column(DateTime, default=datetime.utcnow)
