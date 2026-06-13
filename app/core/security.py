# app/core/security.py
# Pure crypto functions — no FastAPI, no DB dependencies.
# Imported by deps.py and auth_service.py.

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# bcrypt — 12 rounds ≈ 300ms per hash. Good balance of security vs speed.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Hash a plain-text password. Call at user creation and password reset."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Short-lived JWT access token. Default expiry = ACCESS_TOKEN_EXPIRE_MINUTES."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict[str, Any]) -> str:
    """Long-lived JWT refresh token. Expiry = REFRESH_TOKEN_EXPIRE_DAYS."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT. Raises ValueError on expired/invalid token.
    Called in deps.py for every protected endpoint.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError as exc:
        raise ValueError(f"Token validation failed: {exc}") from exc


def create_token_pair(user_id: str, username: str, role: str) -> dict[str, Any]:
    """
    Create access + refresh tokens in one call.
    Returns a dict that maps directly to TokenResponse schema.
    Called by auth_service after successful login.
    """
    payload = {"sub": user_id, "username": username, "role": role}
    return {
        "access_token": create_access_token(payload),
        "refresh_token": create_refresh_token(payload),
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_SECONDS,
    }