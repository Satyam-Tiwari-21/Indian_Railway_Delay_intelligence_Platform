# app/api/v1/auth.py

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.models.db.user import User
from app.models.schemas.auth import TokenRefreshRequest, TokenResponse, UserOut
from app.repositories.user_repository import UserRepository
from app.services.auth_service import (
    authenticate_user,
    create_tokens_for_user,
    log_audit,
    refresh_access_token,
)

router = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and receive JWT tokens",
)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    OAuth2 password flow — sends username + password, receives access + refresh tokens.
    Logs both success and failure to audit_logs.
    """
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    user = authenticate_user(db, form_data.username, form_data.password)

    if user is None:
        log_audit(
            db=db,
            action="AUTH_LOGIN_FAIL",
            username=form_data.username,
            ip_address=ip,
            user_agent=ua,
            response_status=401,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last_login_at
    UserRepository(db).record_login(user.id)

    tokens = create_tokens_for_user(user)

    log_audit(
        db=db,
        action="AUTH_LOGIN",
        user_id=str(user.id),
        username=user.username,
        ip_address=ip,
        user_agent=ua,
        response_status=200,
    )

    return tokens


@router.post(
    "/refresh",
    summary="Get a new access token using a refresh token",
)
def refresh(
    body: TokenRefreshRequest,
    db: Session = Depends(get_db),
):
    """
    Exchange a valid refresh token for a new access token.
    The refresh token itself is not rotated — it stays valid until expiry.
    """
    try:
        return refresh_access_token(db, body.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Log out the current user",
)
def logout(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Logs the logout action to audit_logs.
    JWT tokens are stateless — actual invalidation requires a token blacklist
    (Redis-based). For now, clients should discard tokens on logout.
    """
    log_audit(
        db=db,
        action="AUTH_LOGOUT",
        user_id=str(current_user.id),
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        response_status=200,
    )
    return {"message": "Logged out successfully"}


@router.get(
    "/me",
    response_model=UserOut,
    summary="Get current authenticated user profile",
)
def get_me(current_user: User = Depends(get_current_active_user)):
    """Returns the profile of the currently authenticated user."""
    return UserOut(
        id=str(current_user.id),
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role.name,
        zone_access=current_user.zone_access,
        is_active=current_user.is_active,
        last_login_at=current_user.last_login_at,
    )