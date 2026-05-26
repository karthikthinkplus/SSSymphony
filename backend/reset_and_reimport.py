"""
Reset question bank and re-import EXCLUSIVELY from Adaptive_Math_PnL_Updated.xlsx.
Clears: questions, skills, knowledge_graph, q_matrix, answer_traps,
        question_dimensions (and BKT state, sessions, responses, students
        since they reference old question IDs).
Run: python reset_and_reimport.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ["PYTHONIOENCODING"] = "utf-8"

from app.database import engine, SessionLocal, Base
from app.models import (
    Question, Skill, KnowledgeGraph, QMatrix, AnswerTrap, QuestionDimension,
    BKTState, Response, Session, DimensionScore, Student, AdminUser
)
from app.importer.excel_parser import import_excel

XLSX_PATH = os.path.join(os.path.dirname(__file__), "..", "Adaptive_Math_PnL_Updated.xlsx")

if not os.path.exists(XLSX_PATH):
    print(f"ERROR: File not found: {XLSX_PATH}")
    sys.exit(1)

print("=" * 60)
print("Step 1: Ensuring all tables exist...")
Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    print("Step 2: Clearing existing assessment data...")

    # Clear in dependency order (children first)
    cleared = {}
    cleared["dimension_scores"] = db.query(DimensionScore).delete()
    cleared["bkt_state"] = db.query(BKTState).delete()
    cleared["answer_traps"] = db.query(AnswerTrap).delete()
    cleared["question_dimensions"] = db.query(QuestionDimension).delete()
    cleared["q_matrix"] = db.query(QMatrix).delete()
    cleared["responses"] = db.query(Response).delete()
    db.flush()

    # Sessions and Students reference Questions indirectly — clear them too
    cleared["sessions"] = db.query(Session).delete()
    cleared["students"] = db.query(Student).delete()
    cleared["knowledge_graph"] = db.query(KnowledgeGraph).delete()
    db.flush()

    cleared["questions"] = db.query(Question).delete()
    db.flush()

    cleared["skills"] = db.query(Skill).delete()
    db.flush()

    db.commit()

    for table, n in cleared.items():
        print(f"  Deleted {n:>5} rows from {table}")

    print("\nStep 3: Re-importing from XLSX...")
    result = import_excel(XLSX_PATH, db)

    if result["errors"]:
        print("\nValidation Errors (import ABORTED):")
        for e in result["errors"]:
            print(f"  - {e}")
        sys.exit(1)

    print("\nImport successful!")
    print(f"  Skills imported       : {result['skills_imported']}")
    print(f"  Questions imported    : {result['questions_imported']}")
    print(f"  Q-Matrix rows         : {result['q_matrix_rows']}")
    print(f"  Answer Traps imported : {result['traps_imported']}")
    print(f"  Dimensions imported   : {result['dimensions_imported']}")

    if result["warnings"]:
        print("\nWarnings:")
        for w in result["warnings"]:
            safe = w.encode("ascii", errors="replace").decode("ascii")
            print(f"  - {safe}")

    # Verify
    from app.models import Question as Q2
    final_count = db.query(Q2).count()
    print(f"\nVerification: {final_count} questions now in DB")
    print("\nDefault admin credentials: admin / admin123")
    print("=" * 60)

finally:
    db.close()
