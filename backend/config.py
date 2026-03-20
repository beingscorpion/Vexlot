"""
Root-level config module expected by `backend/main.py` and other imports.

Canonical settings live in `backend/auth/config.py`.
"""

from auth.config import settings  # re-export

__all__ = ["settings"]

