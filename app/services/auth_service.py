# app/services/auth_service.py
# Business logic for authentication.
# Routes call these functions — no FastAPI types here.

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.core.security import (
    create_token_pair,
    create_access_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.db.user import Role, User
from app.models.db.audit_log import AuditLog
from app.repositories.user_repository import UserRepository
from app.core.rbac import ROLE_PERMISSIONS

logger = get_logger(__name__)


# ── Authentication ─────────────────────────────────────────────

def authenticate_user(
    db: Session,
    username: str,
    password: str,
) -> Optional[User]:
    """
    Verify username + password.
    Returns User on success, None on failure.
    Caller is responsible for logging the audit event.
    """
    repo = UserRepository(db)

    # Try username first, then email (users may type either)
    user = repo.get_by_username(username.lower())
    if user is None:
        user = repo.get_by_email(username.lower())

    if user is None:
        logger.warning("Login attempt: user not found", username=username)
        return None

    if not verify_password(password, user.hashed_password):
        logger.warning("Login attempt: wrong password", username=username)
        return None

    if not user.is_active:
        logger.warning("Login attempt: account deactivated", username=username)
        return None

    return user


def create_tokens_for_user(user: User) -> dict:
    """
    Create JWT access + refresh token pair for an authenticated user.
    Returns a dict matching the TokenResponse schema.
    """
    return create_token_pair(
        user_id=str(user.id),
        username=user.username,
        role=user.role.name,
    )


def refresh_access_token(db: Session, refresh_token: str) -> dict:
    """
    Validate a refresh token and issue a new access token.
    Raises ValueError if the refresh token is invalid or expired.
    """
    try:
        payload = decode_token(refresh_token)
    except ValueError as exc:
        raise ValueError(f"Invalid refresh token: {exc}") from exc

    if payload.get("type") != "refresh":
        raise ValueError("Provided token is not a refresh token")

    user_id = payload.get("sub")
    if not user_id:
        raise ValueError("Token missing subject claim")

    user = UserRepository(db).get_with_role(user_id)
    if user is None or not user.is_active:
        raise ValueError("User not found or account deactivated")

    # Issue new access token only (refresh token stays the same)
    token_data = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role.name,
    }
    new_access = create_access_token(token_data)

    from app.core.config import settings
    return {
        "access_token": new_access,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_seconds,
    }


# ── User Management ────────────────────────────────────────────

def create_user(
    db: Session,
    email: str,
    username: str,
    password: str,
    role_id: int,
    full_name: Optional[str] = None,
    zone_access: Optional[str] = None,
) -> User:
    """Create a new user. Called by admin endpoints."""
    repo = UserRepository(db)

    # Check for duplicates
    if repo.get_by_email(email):
        raise ValueError(f"Email '{email}' is already registered")
    if repo.get_by_username(username):
        raise ValueError(f"Username '{username}' is already taken")

    user = repo.create({
        "email": email.lower(),
        "username": username.lower(),
        "hashed_password": get_password_hash(password),
        "full_name": full_name,
        "role_id": role_id,
        "zone_access": zone_access,
        "is_active": True,
    })

    logger.info("User created", user_id=str(user.id), username=username, role_id=role_id)
    return user


# ── Audit Logging ─────────────────────────────────────────────

def log_audit(
    db: Session,
    action: str,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_payload: Optional[dict] = None,
    response_status: Optional[int] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """
    Write a record to audit_logs.
    Call this from services (not routes) so auditing is never skipped.
    Swallows exceptions — audit failure should never break the main flow.
    """
    try:
        db.add(AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_payload=request_payload,
            response_status=response_status,
            duration_ms=duration_ms,
        ))
        db.flush()
    except Exception as exc:
        logger.error("Failed to write audit log", action=action, error=str(exc))


# ── DB Seeding (run once after alembic upgrade head) ───────────

def seed_roles(db: Session) -> None:
    """
    Insert the four default roles if they don't already exist.
    Safe to run multiple times — skips existing roles.
    """
    repo = UserRepository(db)
    for role_name, permissions in ROLE_PERMISSIONS.items():
        if repo.get_role_by_name(role_name) is None:
            db.add(Role(
                name=role_name,
                description=f"Default {role_name} role",
                permissions=permissions,
            ))
            logger.info("Created role", role=role_name)
    db.flush()


def seed_admin_user(
    db: Session,
    email: str = "admin@railways.in",
    username: str = "admin",
    password: str = "Admin@12345",
) -> None:
    """
    Create the initial admin user if it doesn't exist.
    CHANGE the password immediately after first login.
    """
    repo = UserRepository(db)
    if repo.get_by_username(username):
        logger.info("Admin user already exists, skipping seed")
        return

    admin_role = repo.get_role_by_name("admin")
    if not admin_role:
        raise RuntimeError("Run seed_roles() before seed_admin_user()")

    create_user(
        db=db,
        email=email,
        username=username,
        password=password,
        role_id=admin_role.id,
        full_name="System Administrator",
    )
    logger.info("Admin user created", username=username)