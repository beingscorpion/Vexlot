"""
Root-level crypto/JWT utilities module.

Canonical implementation lives in `backend/auth/security.py`.
"""

from auth.security import (  # re-export
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)

__all__ = [
    "create_access_token",
    "create_refresh_token",
    "decode_access_token",
    "hash_password",
    "hash_refresh_token",
    "verify_password",
]

