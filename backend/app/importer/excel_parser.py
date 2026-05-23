"""
Excel Parser — ingests the 5-sheet SME Template workbook.

Sheet mapping:
  1_Skills         → skills + knowledge_graph
  2_Questions      → questions
  3_Q_Matrix       → q_matrix
  4_AnswerTraps    → answer_traps
  5_Dimensions     → question_dimensions
"""

import pandas as pd
from typing import Dict, List, Tuple, Any
from sqlalchemy.orm import Session as DBSession

from app.models import (
    Skill, KnowledgeGraph, Question, QMatrix,
    AnswerTrap, QuestionDimension,
)
from app.importer.validator import validate_all


def _bool(val) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().upper() in ("YES", "1", "TRUE", "Y")
    return False


def _str(val) -> str:
    if pd.isna(val):
        return ""
    return str(val).strip()


def _int(val, default=None):
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def parse_excel(file_path: str) -> Dict[str, pd.DataFrame]:
    """Load all sheets from the workbook, skipping title rows (header at row 2)."""
    xl = pd.ExcelFile(file_path)
    sheets = {}
    for sheet in xl.sheet_names:
        key = sheet.strip()
        # Try header=2 first (SME template format has 2 title rows before column names)
        try:
            df = xl.parse(sheet, header=2)
            # If the first column looks like it's still metadata, fallback to header=0
            if df.empty or (len(df.columns) > 0 and str(df.columns[0]).startswith('SHEET')):
                df = xl.parse(sheet, header=0)
        except Exception:
            df = xl.parse(sheet, header=0)
        # Normalise column names: strip whitespace AND newlines
        df.columns = [str(c).strip().replace('\n', ' ') for c in df.columns]
        sheets[key] = df
    return sheets


def _find_sheet(sheets: Dict, *candidates) -> Tuple[str, pd.DataFrame]:
    for c in candidates:
        for k, v in sheets.items():
            if c.lower() in k.lower():
                return k, v
    raise ValueError(f"Could not find sheet matching any of: {candidates}")


def import_excel(file_path: str, db: DBSession) -> Dict[str, Any]:
    """
    Parse, validate, and import all 5 sheets into the database.
    Returns a summary dict with counts and errors.
    """
    sheets = parse_excel(file_path)
    errors, warnings = validate_all(sheets)

    result = {
        "success": len(errors) == 0,
        "skills_imported": 0,
        "questions_imported": 0,
        "traps_imported": 0,
        "dimensions_imported": 0,
        "q_matrix_rows": 0,
        "errors": errors,
        "warnings": warnings,
    }

    if errors:
        return result

    # -----------------------------------------------------------------------
    # Sheet 1 — Skills
    # -----------------------------------------------------------------------
    _, skills_df = _find_sheet(sheets, "1_Skills", "skills", "Skills")
    skills_df.columns = [str(c).strip() for c in skills_df.columns]

    for _, row in skills_df.iterrows():
        sid = _str(row.get("skill_id", ""))
        if not sid:
            continue
        existing = db.query(Skill).filter(Skill.skill_id == sid).first()
        if existing:
            skill = existing
        else:
            skill = Skill(skill_id=sid)
            db.add(skill)
        skill.skill_name = _str(row.get("skill_name", ""))
        skill.grade_level = _str(row.get("grade_level", ""))
        skill.topic_area = _str(row.get("topic_area", ""))
        skill.difficulty_band = _str(row.get("difficulty_band", ""))
        skill.prerequisite_skill_ids = _str(row.get("prerequisite_skill_ids", ""))
        skill.notes = _str(row.get("notes", ""))
        result["skills_imported"] += 1

    db.flush()

    # Build knowledge_graph edges
    for _, row in skills_df.iterrows():
        child_id = _str(row.get("skill_id", ""))
        prereqs_raw = _str(row.get("prerequisite_skill_ids", ""))
        if not child_id or not prereqs_raw:
            continue
        for parent_id in [p.strip() for p in prereqs_raw.split(",") if p.strip()]:
            exists = (
                db.query(KnowledgeGraph)
                .filter(
                    KnowledgeGraph.child_skill_id == child_id,
                    KnowledgeGraph.parent_skill_id == parent_id,
                )
                .first()
            )
            if not exists:
                db.add(KnowledgeGraph(child_skill_id=child_id, parent_skill_id=parent_id))

    db.flush()

    # -----------------------------------------------------------------------
    # Sheet 2 — Questions
    # -----------------------------------------------------------------------
    _, questions_df = _find_sheet(sheets, "2_Questions", "questions", "Questions")
    questions_df.columns = [str(c).strip() for c in questions_df.columns]

    for _, row in questions_df.iterrows():
        qid = _str(row.get("question_id", ""))
        if not qid:
            continue
        existing = db.query(Question).filter(Question.question_id == qid).first()
        if existing:
            q = existing
        else:
            q = Question(question_id=qid)
            db.add(q)
        q.question_text = _str(row.get("question_text", ""))
        q.question_type = _str(row.get("question_type", "MCQ"))
        q.word_problem_flag = _bool(row.get("word_problem_flag", False))
        twin_raw = _str(row.get("equation_twin_id", ""))
        q.equation_twin_id = twin_raw if twin_raw else None
        q.primary_skill_id = _str(row.get("primary_skill_id", "")) or None
        q.secondary_skill_ids = _str(row.get("secondary_skill_ids", ""))
        q.grade_level = _int(row.get("grade_level"))
        q.difficulty_band = _str(row.get("difficulty_band", "medium"))
        q.option_a = _str(row.get("option_A", row.get("option_a", "")))
        q.option_b = _str(row.get("option_B", row.get("option_b", "")))
        q.option_c = _str(row.get("option_C", row.get("option_c", "")))
        q.option_d = _str(row.get("option_D", row.get("option_d", "")))
        q.correct_option = _str(row.get("correct_option", "")).upper()[:1]
        result["questions_imported"] += 1

    db.flush()

    # -----------------------------------------------------------------------
    # Sheet 3 — Q-Matrix
    # -----------------------------------------------------------------------
    _, qmatrix_df = _find_sheet(sheets, "3_Q_Matrix", "q_matrix", "Q_Matrix", "QMatrix")
    qmatrix_df.columns = [str(c).strip() for c in qmatrix_df.columns]

    # Identify skill columns (those starting with S_ followed by digits)
    import re
    skill_cols = [c for c in qmatrix_df.columns if re.match(r'^S_\d+', c)]

    for _, row in qmatrix_df.iterrows():
        qid = _str(row.get("question_id", ""))
        if not qid:
            continue
        for scol in skill_cols:
            val = row.get(scol, 0)
            try:
                if int(float(val)) == 1:
                    # Extract clean skill_id (e.g. "S_001" from "S_001 Arithmetic Progression")
                    skill_id = scol.split()[0] if ' ' in scol else scol
                    exists = (
                        db.query(QMatrix)
                        .filter(QMatrix.question_id == qid, QMatrix.skill_id == skill_id)
                        .first()
                    )
                    if not exists:
                        db.add(QMatrix(question_id=qid, skill_id=skill_id))
                        result["q_matrix_rows"] += 1
            except (ValueError, TypeError):
                continue

    db.flush()

    # -----------------------------------------------------------------------
    # Sheet 4 — Answer Traps
    # -----------------------------------------------------------------------
    _, traps_df = _find_sheet(sheets, "4_AnswerTraps", "answer_traps", "AnswerTraps", "Traps")
    traps_df.columns = [str(c).strip() for c in traps_df.columns]

    for _, row in traps_df.iterrows():
        qid = _str(row.get("question_id", ""))
        opt = _str(row.get("option_label", "")).upper()[:1]
        if not qid or not opt:
            continue
        existing = (
            db.query(AnswerTrap)
            .filter(AnswerTrap.question_id == qid, AnswerTrap.option_label == opt)
            .first()
        )
        if existing:
            trap = existing
        else:
            trap = AnswerTrap(question_id=qid, option_label=opt)
            db.add(trap)
        trap.option_text = _str(row.get("option_text", ""))
        trap.trap_type = _str(row.get("trap_type", ""))
        gap_id = _str(row.get("skill_gap_id", ""))
        trap.skill_gap_id = gap_id if gap_id else None
        trap.misconception = _str(row.get("misconception", ""))
        trap.misconception_detail = _str(row.get("misconception_detail", ""))
        trap.remedial_action = _str(row.get("remedial_action", "serve_same_level"))
        rem_skill = _str(row.get("remedial_skill_id", ""))
        trap.remedial_skill_id = rem_skill if rem_skill else None
        trap.remedial_grade = _int(row.get("remedial_grade"))
        result["traps_imported"] += 1

    db.flush()

    # -----------------------------------------------------------------------
    # Sheet 5 — Dimensions
    # -----------------------------------------------------------------------
    _, dims_df = _find_sheet(sheets, "5_Dimensions", "dimensions", "Dimensions")
    dims_df.columns = [str(c).strip() for c in dims_df.columns]

    for _, row in dims_df.iterrows():
        qid = _str(row.get("question_id", ""))
        if not qid:
            continue
        existing = (
            db.query(QuestionDimension)
            .filter(QuestionDimension.question_id == qid)
            .first()
        )
        if existing:
            dim = existing
        else:
            dim = QuestionDimension(question_id=qid)
            db.add(dim)
        dim.dim_reading = _bool(row.get("dim_reading", 0))
        dim.dim_understanding = _bool(row.get("dim_understanding", 0))
        dim.dim_application = _bool(row.get("dim_application", 0))
        dim.dim_calculation = _bool(row.get("dim_calculation", 0))
        dim.dim_retention = _bool(row.get("dim_retention", 0))
        dim.primary_dimension = _str(row.get("primary_dimension", ""))
        pair_id = _str(row.get("word_eq_pair_id", ""))
        dim.word_eq_pair_id = pair_id if pair_id else None
        result["dimensions_imported"] += 1

    db.commit()
    return result
