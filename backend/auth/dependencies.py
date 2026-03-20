# ── dependencies.py ──────────────────────────────────────────────────────────
# Reusable FastAPI dependencies injected via Depends().
# Most routes will use get_current_active_user as their auth guard.

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from database import get_db
from models import User
from security import decode_access_token


# ── Bearer token extractor ────────────────────────────────────────────────────
_bearer = HTTPBearer(auto_error=False)


def _get_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Pull the raw JWT string from the Authorization header."""
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


# ── Current user dependency ───────────────────────────────────────────────────
def get_current_user(
    token: str = Depends(_get_token),
    db: Session = Depends(get_db),
) -> User:
    """
    Decode the JWT, look up the user in the DB, and return the ORM object.
    Raises 401 for any token problem, 404 if the user no longer exists.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = db.get(User, int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Additional guard: reject deactivated accounts.
    Drop this into any route that should be inaccessible after account suspension.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )
    return current_user


def get_request_meta(request: Request) -> dict:
    """
    Extract IP address and User-Agent from the incoming request.
    Stored alongside refresh tokens for session display.
    """
    ip = request.client.host if request.client else None
    # honour X-Forwarded-For if behind a reverse proxy
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()

    user_agent = request.headers.get("User-Agent", "")[:500]
    return {"ip_address": ip, "user_agent": user_agent}
