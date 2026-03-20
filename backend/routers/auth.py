"""
Thin wrapper so `backend/main.py` can include auth routes.

Canonical router is in `backend/auth/auth.py`.
"""

from auth.auth import router

__all__ = ["router"]

