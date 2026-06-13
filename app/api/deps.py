# app/api/deps.py
# All FastAPI Depends() functions used across route files.
# Import from here, not from security.py or database.py directly.

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.core.logging_config import get_logger
from app.models.db.user import User
from app.repositories.user_repository import UserRepository

logger = get_logger(__name__)

# Re-export get_db so routes only import from one place
__all__ = [
    "get_db",
    "get_current_user",
    "get_current_active_user",
    "require_permission",
    "require_admin",
]

# tokenUrl must match the login endpoint path
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ── Core User Dependencies ─────────────────────────────────────

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Decode JWT, load user from DB.
    Raises 401 if token is invalid, expired, or user doesn't exist.
    Used on every protected endpoint.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id: Optional[str] = payload.get("sub")
        token_type: Optional[str] = payload.get("type")

        if user_id is None:
            raise credentials_exc
        # Reject refresh tokens used as access tokens
        if token_type != "access":
            raise credentials_exc
    except ValueError:
        raise credentials_exc

    user = UserRepository(db).get_with_role(user_id)
    if user is None:
        raise credentials_exc

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Extends get_current_user — also checks is_active=True.
    Raises 403 if the account has been deactivated by an admin.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Contact an administrator.",
        )
    return current_user


# ── Permission Dependency Factory ──────────────────────────────

def require_permission(permission: str):
    """
    Returns a FastAPI dependency that checks a specific permission.
    The user object is returned so it's available in the route body.

    Usage:
        @router.post("/predict")
        def predict(
            user: User = Depends(require_permission("can_predict")),
            db: Session = Depends(get_db),
        ):
    """
    def _dependency(user: User = Depends(get_current_active_user)) -> User:
        if not user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Your role '{user.role.name}' does not have "
                    f"the '{permission}' permission required for this action."
                ),
            )
        return user

    return _dependency


def require_admin(user: User = Depends(get_current_active_user)) -> User:
    """
    Admin-only hard gate (checks role name, not just permissions).
    Use this for user management and system config endpoints.
    """
    if user.role.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required for this endpoint.",
        )
    return user