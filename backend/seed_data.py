"""
Seed script - imports the provided XLSX workbook into the database.
Run once: python seed_data.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.database import engine, SessionLocal, Base
from app.models import *  # ensure all models registered
from app.importer.excel_parser import import_excel

Base.metadata.create_all(bind=engine)

XLSX_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "Adaptive_Math_PnL_Updated.xlsx",
)

if not os.path.exists(XLSX_PATH):
    print(f"ERROR: XLSX file not found at {XLSX_PATH}")
    sys.exit(1)

print(f"Importing from: {os.path.abspath(XLSX_PATH)}")
db = SessionLocal()
result = None
try:
    result = import_excel(XLSX_PATH, db)
    if result["errors"]:
        print("\nValidation Errors:")
        for e in result["errors"]:
            print(f"  - {e}")
    else:
        print("\nImport successful!")
        print(f"  Skills imported       : {result['skills_imported']}")
        print(f"  Questions imported    : {result['questions_imported']}")
        print(f"  Q-Matrix rows         : {result['q_matrix_rows']}")
        print(f"  Answer Traps imported : {result['traps_imported']}")
        print(f"  Dimensions imported   : {result['dimensions_imported']}")

    if result["warnings"]:
        print("\nWarnings:")
        for w in result["warnings"]:
            safe_w = w.encode('ascii', errors='replace').decode('ascii')
            print(f"  - {safe_w}")
finally:
    db.close()

print("\nDefault admin credentials: admin / admin123")
print("Start the server: uvicorn app.main:app --reload --port 8000")
