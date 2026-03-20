"""
Wrapper module to satisfy:
`from services import auth_service` used by `backend/auth/auth.py`.

Canonical implementation lives in `backend/auth/auth_service.py`.
"""

from auth.auth_service import *  # noqa: F403

