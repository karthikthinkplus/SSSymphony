"""
FastAPI application entry point.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base, SessionLocal
from app.models import AdminUser
from app.routers import session as session_router, admin as admin_router
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _seed_admin():
    """Create a default admin user if none exists."""
    db = SessionLocal()
    try:
        exists = db.query(AdminUser).filter(AdminUser.username == "admin").first()
        if not exists:
            default_pw = os.getenv("ADMIN_DEFAULT_PASSWORD", "changeme")
            admin = AdminUser(
                username="admin",
                hashed_password=_hash_password(default_pw),
                role="admin",
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables
    Base.metadata.create_all(bind=engine)
    _seed_admin()
    yield


app = FastAPI(
    title="Adaptive Math Assessment Tool",
    description="CAT/IRT + CDM + BKT + DKT diagnostic engine for NCERT-aligned mathematics",
    version="1.0.0",
    lifespan=lifespan,
)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session_router.router)
app.include_router(admin_router.router)


@app.get("/")
def root():
    return {
        "name": "Adaptive Math Assessment Tool API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
