# ── security.py ──────────────────────────────────────────────────────────────
# Low-level cryptographic helpers.
# Nothing in here should import from routers or services — keep it pure utility.

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from config import settings


# ── Password hashing ──────────────────────────────────────────────────────────
def _bcrypt_plain_bytes(plain: str) -> bytes:
    """
    bcrypt only supports the first 72 bytes of the password.

    We truncate explicitly to avoid runtime ValueError for long passwords.
    """
    pw_bytes = plain.encode("utf-8")
    return pw_bytes[:72] if len(pw_bytes) > 72 else pw_bytes


def hash_password(plain: str) -> str:
    """Return a bcrypt hash for the given password."""
    salt = bcrypt.gensalt()
    pw_bytes = _bcrypt_plain_bytes(plain)
    hashed = bcrypt.hashpw(pw_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the stored bcrypt *hashed* value."""
    pw_bytes = _bcrypt_plain_bytes(plain)
    try:
        return bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))
    except ValueError:
        # Stored hash is malformed/unknown format.
        return False


# ── JWT ───────────────────────────────────────────────────────────────────────
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    subject: int | str,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, datetime]:
    """
    Create a signed JWT access token.

    Parameters
    ----------
    subject   : user id (stored as the JWT "sub" claim)
    extra_claims : any additional claims to embed (e.g. {"role": "owner"})

    Returns
    -------
    (encoded_jwt, expires_at)
    """
    expires_at = _utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub":  str(subject),
        "iat":  _utcnow(),
        "exp":  expires_at,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expires_at


def create_refresh_token() -> tuple[str, str, datetime]:
    """
    Create an opaque refresh token.

    We do NOT use a JWT here — opaque tokens are safer for refresh because
    they can be truly revoked (we check the hash against the DB on every use).

    Returns
    -------
    (raw_token, sha256_hash, expires_at)
    The *raw_token* goes to the client; only the *hash* is stored in the DB.
    """
    raw = secrets.token_urlsafe(64)
    token_hash = _hash_token(raw)
    expires_at = _utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return raw, token_hash, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT access token.

    Raises
    ------
    jose.JWTError  – if the token is invalid, expired, or tampered with.
    """
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    if payload.get("type") != "access":
        raise JWTError("Token type mismatch — expected access token.")
    return payload


def _hash_token(raw: str) -> str:
    """SHA-256 hash an opaque token for safe storage."""
    return hashlib.sha256(raw.encode()).hexdigest()


def hash_refresh_token(raw: str) -> str:
    """Public wrapper around _hash_token for use in services."""
    return _hash_token(raw)
