"""
Root-level database module expected by `backend/main.py` and other imports.

Canonical DB wiring (engine, Base, session dependency) lives in `backend/auth/database.py`.
"""

from auth.database import Base, SessionLocal, engine, get_db  # re-export

__all__ = ["Base", "SessionLocal", "engine", "get_db"]

