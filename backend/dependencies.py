"""
Root-level FastAPI dependencies module.

Canonical dependencies live in `backend/auth/dependencies.py`.
"""

from auth.dependencies import (  # re-export
    get_current_active_user,
    get_current_user,
    get_request_meta,
)

__all__ = [
    "get_current_active_user",
    "get_current_user",
    "get_request_meta",
]

