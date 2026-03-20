# ── routers/auth.py ───────────────────────────────────────────────────────────
# All authentication endpoints live here.
# Routes are thin: validate input → call service → return response.

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_active_user, get_request_meta
from models import User
from schemas import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    SessionInfo,
    TokenResponse,
    UserResponse,
    UserUpdateRequest,
)
from services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── POST /auth/register ───────────────────────────────────────────────────────
@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new Verdant account.

    - Email must be unique.
    - Password must be ≥ 8 characters, contain an uppercase letter and a digit.
    - Account starts unverified (add email flow later).
    """
    user = auth_service.register_user(payload, db)
    return RegisterResponse(user=UserResponse.model_validate(user))


# ── POST /auth/login ──────────────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Log in and receive access + refresh tokens",
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
    meta: dict = Depends(get_request_meta),
):
    """
    Authenticate with email + password.

    Returns:
    - **access_token** (JWT, short-lived — 30 min default)
    - **refresh_token** (opaque, long-lived — 7 days default)

    Pass the access token as `Authorization: Bearer <token>` on protected routes.
    """
    result = auth_service.login_user(payload, db, meta["ip_address"], meta["user_agent"])
    return LoginResponse(
        user=UserResponse.model_validate(result["user"]),
        tokens=TokenResponse(**result["tokens"]),
    )


# ── POST /auth/refresh ────────────────────────────────────────────────────────
@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token and get a new access token",
)
def refresh(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
    meta: dict = Depends(get_request_meta),
):
    """
    Exchange a valid refresh token for a brand-new access + refresh token pair.

    The old refresh token is **revoked** immediately (rotation pattern).
    If the same refresh token is used twice, all sessions are revoked
    as a security measure against token theft.
    """
    tokens = auth_service.refresh_access_token(payload, db, meta["ip_address"], meta["user_agent"])
    return TokenResponse(**tokens)


# ── POST /auth/logout ─────────────────────────────────────────────────────────
@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Log out the current device",
)
def logout(
    payload: RefreshRequest,
    _: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Revoke the supplied refresh token, effectively logging out this device.
    The access token will expire on its own (stateless JWT — cannot be revoked).
    """
    auth_service.logout_user(payload.refresh_token, db)
    return LogoutResponse()


# ── POST /auth/logout-all ─────────────────────────────────────────────────────
@router.post(
    "/logout-all",
    response_model=LogoutResponse,
    summary="Log out from all devices",
)
def logout_all(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Revoke **all** refresh tokens for this user.
    Use this when a user suspects their account has been compromised.
    """
    auth_service.logout_all_devices(current_user.id, db)
    return LogoutResponse(message="Logged out from all devices.")


# ── GET /auth/me ──────────────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the current authenticated user",
)
def get_me(current_user: User = Depends(get_current_active_user)):
    """Return the profile of the currently authenticated user."""
    return UserResponse.model_validate(current_user)


# ── PATCH /auth/me ────────────────────────────────────────────────────────────
@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update profile (name fields)",
)
def update_me(
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update first_name and/or last_name for the authenticated user."""
    updated = auth_service.update_profile(current_user, payload, db)
    return UserResponse.model_validate(updated)


# ── POST /auth/change-password ────────────────────────────────────────────────
@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change password (requires current password)",
)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Change the authenticated user's password.

    - Validates the current password first.
    - Revokes all refresh tokens after success (force re-login on all devices).
    """
    auth_service.change_password(current_user, payload, db)
    return MessageResponse(message="Password changed successfully. Please log in again on all devices.")


# ── GET /auth/sessions ────────────────────────────────────────────────────────
@router.get(
    "/sessions",
    response_model=list[SessionInfo],
    summary="List all active sessions (refresh tokens)",
)
def list_sessions(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Return all non-expired, non-revoked refresh tokens for this user."""
    sessions = auth_service.get_active_sessions(current_user.id, db)
    return [SessionInfo.model_validate(s) for s in sessions]


# ── DELETE /auth/me ───────────────────────────────────────────────────────────
@router.delete(
    "/me",
    response_model=MessageResponse,
    summary="Permanently delete account",
)
def delete_account(
    password: str = Body(..., embed=True, description="Confirm with your current password"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Permanently delete the authenticated user's account and all associated data.
    Requires password confirmation.
    """
    auth_service.delete_account(current_user, password, db)
    return MessageResponse(message="Account deleted permanently.")
