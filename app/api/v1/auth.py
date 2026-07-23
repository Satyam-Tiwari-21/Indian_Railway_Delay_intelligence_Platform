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


@router.post("/login", response_model=TokenResponse)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    user = authenticate_user(db, form_data.username, form_data.password)

    if user is None:
        log_audit(db=db, action="AUTH_LOGIN_FAIL",
                  username=form_data.username, ip_address=ip,
                  user_agent=ua, response_status=401)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    UserRepository(db).record_login(user.id)
    tokens = create_tokens_for_user(user)
    log_audit(db=db, action="AUTH_LOGIN", user_id=str(user.id),
              username=user.username, ip_address=ip,
              user_agent=ua, response_status=200)
    return tokens


@router.post("/refresh")
def refresh(body: TokenRefreshRequest, db: Session = Depends(get_db)):
    try:
        return refresh_access_token(db, body.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    log_audit(db=db, action="AUTH_LOGOUT", user_id=str(current_user.id),
              username=current_user.username,
              ip_address=request.client.host if request.client else None,
              response_status=200)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_active_user)):
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