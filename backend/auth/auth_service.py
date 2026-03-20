# ── services/auth_service.py ─────────────────────────────────────────────────
# Business logic layer for auth.
# Routers call these functions — they never touch the DB directly.
# This separation makes the logic unit-testable without spinning up a server.

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import RefreshToken, User
from schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    UserUpdateRequest,
)
from security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from config import settings


# ── Internal helpers ──────────────────────────────────────────────────────────
def _build_token_pair(user: User, db: Session, ip: str | None, ua: str | None) -> dict:
    """
    Create a fresh access + refresh token pair, persist the refresh token,
    and return a dict matching TokenResponse fields.
    """
    access_token, expires_at = create_access_token(subject=user.id)
    raw_refresh, refresh_hash, refresh_expires = create_refresh_token()

    db_refresh = RefreshToken(
        token_hash=refresh_hash,
        user_id=user.id,
        expires_at=refresh_expires,
        ip_address=ip,
        user_agent=ua,
    )
    db.add(db_refresh)
    db.commit()

    expires_in = int(settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    return {
        "access_token":  access_token,
        "refresh_token": raw_refresh,
        "token_type":    "bearer",
        "expires_in":    expires_in,
    }


# ── Register ──────────────────────────────────────────────────────────────────
def register_user(payload: RegisterRequest, db: Session) -> User:
    # Check for duplicate email
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        is_active=True,
        is_verified=False,   # flip to True once you add email verification
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ── Login ─────────────────────────────────────────────────────────────────────
def login_user(
    payload: LoginRequest,
    db: Session,
    ip: str | None,
    ua: str | None,
) -> dict:
    user = db.query(User).filter(User.email == payload.email.lower()).first()

    # Use a constant-time check to prevent user-enumeration via timing attacks
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact support.",
        )

    tokens = _build_token_pair(user, db, ip, ua)
    return {"user": user, "tokens": tokens}


# ── Refresh ───────────────────────────────────────────────────────────────────
def refresh_access_token(
    payload: RefreshRequest,
    db: Session,
    ip: str | None,
    ua: str | None,
) -> dict:
    token_hash = hash_refresh_token(payload.refresh_token)

    db_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .first()
    )

    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        )

    if db_token.revoked:
        # Possible token reuse — revoke ALL tokens for this user (security measure)
        _revoke_all_user_tokens(db_token.user_id, db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token already used. All sessions have been revoked.",
        )

    if db_token.is_expired:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please log in again.",
        )

    # Rotate: revoke the old token, issue a new pair
    db_token.revoked = True
    db.commit()

    user = db.get(User, db_token.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not found or deactivated.",
        )

    return _build_token_pair(user, db, ip, ua)


# ── Logout ────────────────────────────────────────────────────────────────────
def logout_user(refresh_token_raw: str, db: Session) -> None:
    """Revoke a single refresh token (logs out one device)."""
    token_hash = hash_refresh_token(refresh_token_raw)
    db_token = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if db_token and not db_token.revoked:
        db_token.revoked = True
        db.commit()


def logout_all_devices(user_id: int, db: Session) -> None:
    """Revoke every refresh token for a user (logs out all devices)."""
    _revoke_all_user_tokens(user_id, db)


def _revoke_all_user_tokens(user_id: int, db: Session) -> None:
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked == False,         # noqa: E712
    ).update({"revoked": True})
    db.commit()


# ── Get active sessions ───────────────────────────────────────────────────────
def get_active_sessions(user_id: int, db: Session) -> list[RefreshToken]:
    # SQLite typically returns timezone-naive datetimes from DateTime(timezone=True).
    # Use a naive "now" to keep the comparison compatible.
    now = datetime.utcnow()
    return (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False,       # noqa: E712
            RefreshToken.expires_at > now,
        )
        .order_by(RefreshToken.created_at.desc())
        .all()
    )


# ── Change password ───────────────────────────────────────────────────────────
def change_password(
    user: User,
    payload: ChangePasswordRequest,
    db: Session,
) -> None:
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must differ from the current password.",
        )

    user.hashed_password = hash_password(payload.new_password)
    # Revoke all refresh tokens so other devices are forced to re-login
    _revoke_all_user_tokens(user.id, db)
    db.commit()


# ── Update profile ────────────────────────────────────────────────────────────
def update_profile(
    user: User,
    payload: UserUpdateRequest,
    db: Session,
) -> User:
    if payload.first_name is not None:
        user.first_name = payload.first_name.strip()
    if payload.last_name is not None:
        user.last_name = payload.last_name.strip()
    db.commit()
    db.refresh(user)
    return user


# ── Delete account ────────────────────────────────────────────────────────────
def delete_account(user: User, password: str, db: Session) -> None:
    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password confirmation failed.",
        )
    db.delete(user)   # cascade will remove refresh_tokens too
    db.commit()
