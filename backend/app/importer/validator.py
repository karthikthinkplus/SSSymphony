"""
Validator — checks all 5 sheets before import.

Returns (errors: List[str], warnings: List[str]).
"""

import pandas as pd
import re
from typing import Dict, List, Tuple

REQUIRED_SKILLS_COLS = ["skill_id", "skill_name", "grade_level"]
REQUIRED_QUESTIONS_COLS = ["question_id", "question_text", "primary_skill_id", "grade_level", "difficulty_band"]
REQUIRED_TRAPS_COLS = ["question_id", "option_label", "trap_type"]
REQUIRED_DIMS_COLS = ["question_id"]


def _find_df(sheets: Dict, *keys) -> Tuple[bool, pd.DataFrame]:
    for k in keys:
        for name, df in sheets.items():
            if k.lower() in name.lower():
                return True, df
    return False, pd.DataFrame()


def validate_all(sheets: Dict) -> Tuple[List[str], List[str]]:
    errors = []
    warnings = []

    # Check all 5 sheets exist
    sheet_checks = [
        ("1_Skills", ["1_Skills", "skills", "Skills"]),
        ("2_Questions", ["2_Questions", "questions", "Questions"]),
        ("3_Q_Matrix", ["3_Q_Matrix", "q_matrix", "Q_Matrix", "QMatrix"]),
        ("4_AnswerTraps", ["4_AnswerTraps", "answer_traps", "AnswerTraps", "Traps"]),
        ("5_Dimensions", ["5_Dimensions", "dimensions", "Dimensions"]),
    ]
    for label, candidates in sheet_checks:
        found, _ = _find_df(sheets, *candidates)
        if not found:
            errors.append(f"Missing required sheet: {label}")

    if errors:
        return errors, warnings

    # Sheet 1 — Skills
    found, skills_df = _find_df(sheets, "1_Skills", "skills", "Skills")
    skills_df.columns = [str(c).strip() for c in skills_df.columns]
    for col in REQUIRED_SKILLS_COLS:
        if col not in skills_df.columns:
            errors.append(f"Sheet 1_Skills: missing required column '{col}'")
        else:
            null_rows = skills_df[skills_df[col].isna()].index.tolist()
            for r in null_rows:
                errors.append(f"Sheet 1_Skills row {r+2}: '{col}' is empty")

    skill_ids = set()
    if "skill_id" in skills_df.columns:
        for _, row in skills_df.iterrows():
            sid = str(row.get("skill_id", "")).strip()
            if sid:
                skill_ids.add(sid)

    # Sheet 2 — Questions
    found, questions_df = _find_df(sheets, "2_Questions", "questions", "Questions")
    questions_df.columns = [str(c).strip() for c in questions_df.columns]
    for col in REQUIRED_QUESTIONS_COLS:
        if col not in questions_df.columns:
            errors.append(f"Sheet 2_Questions: missing required column '{col}'")

    q_ids = set()
    if "question_id" in questions_df.columns:
        for _, row in questions_df.iterrows():
            qid = str(row.get("question_id", "")).strip()
            if qid:
                q_ids.add(qid)
        # Check FK: primary_skill_id must exist in skills
        if "primary_skill_id" in questions_df.columns and skill_ids:
            for i, row in questions_df.iterrows():
                sid = str(row.get("primary_skill_id", "")).strip()
                if sid and sid not in skill_ids:
                    warnings.append(
                        f"Sheet 2_Questions row {i+2}: primary_skill_id '{sid}' not in Skills sheet"
                    )

    # Sheet 3 — Q-Matrix: just check question_id column exists
    found, qm_df = _find_df(sheets, "3_Q_Matrix", "q_matrix", "Q_Matrix", "QMatrix")
    qm_df.columns = [str(c).strip() for c in qm_df.columns]
    if "question_id" not in qm_df.columns:
        errors.append("Sheet 3_Q_Matrix: missing 'question_id' column")

    # Sheet 4 — Answer Traps
    found, traps_df = _find_df(sheets, "4_AnswerTraps", "answer_traps", "AnswerTraps", "Traps")
    traps_df.columns = [str(c).strip() for c in traps_df.columns]
    for col in REQUIRED_TRAPS_COLS:
        if col not in traps_df.columns:
            errors.append(f"Sheet 4_AnswerTraps: missing required column '{col}'")

    # Sheet 5 — Dimensions
    found, dims_df = _find_df(sheets, "5_Dimensions", "dimensions", "Dimensions")
    dims_df.columns = [str(c).strip() for c in dims_df.columns]
    for col in REQUIRED_DIMS_COLS:
        if col not in dims_df.columns:
            errors.append(f"Sheet 5_Dimensions: missing required column '{col}'")

    return errors, warnings
