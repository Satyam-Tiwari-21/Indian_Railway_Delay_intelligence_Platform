# app/api/v1/admin.py

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.core.database import check_db_connection
from app.models.db.audit_log import AuditLog
from app.models.db.user import User
from app.models.schemas.auth import UserCreate, UserOut, UserUpdate
from app.repositories.user_repository import UserRepository
from app.services.auth_service import create_user, log_audit

router = APIRouter()


# ── User Management ────────────────────────────────────────────

@router.get(
    "/users",
    response_model=list[UserOut],
    summary="List all users (admin only)",
)
def list_users(
    skip: int = 0,
    limit: int = Query(100, le=500),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = UserRepository(db).get_all_active(skip=skip, limit=limit)
    return [
        UserOut(
            id=str(u.id),
            email=u.email,
            username=u.username,
            full_name=u.full_name,
            role=u.role.name,
            zone_access=u.zone_access,
            is_active=u.is_active,
            last_login_at=u.last_login_at,
        )
        for u in users
    ]


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (admin only)",
)
def create_new_user(
    body: UserCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        user = create_user(
            db=db,
            email=body.email,
            username=body.username,
            password=body.password,
            role_id=body.role_id,
            full_name=body.full_name,
            zone_access=body.zone_access,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    log_audit(
        db=db,
        action="ADMIN_CREATE_USER",
        user_id=str(admin.id),
        username=admin.username,
        resource_type="user",
        resource_id=str(user.id),
        response_status=201,
    )

    return UserOut(
        id=str(user.id),
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=user.role.name,
        zone_access=user.zone_access,
        is_active=user.is_active,
        last_login_at=None,
    )


@router.put(
    "/users/{user_id}",
    response_model=UserOut,
    summary="Update a user's role, zone, or active status (admin only)",
)
def update_user(
    user_id: str,
    body: UserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    repo = UserRepository(db)
    user = repo.get_with_role(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    updates = body.model_dump(exclude_none=True)
    repo.update(user, updates)

    log_audit(
        db=db, action="ADMIN_UPDATE_USER",
        user_id=str(admin.id), username=admin.username,
        resource_type="user", resource_id=user_id,
        request_payload=updates, response_status=200,
    )

    # Refresh role relationship
    db.refresh(user)
    return UserOut(
        id=str(user.id),
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=user.role.name if user.role else "viewer",
        zone_access=user.zone_access,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
    )


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Deactivate a user — soft delete (admin only)",
)
def deactivate_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == str(admin.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )
    repo = UserRepository(db)
    if repo.get(user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    repo.deactivate(user_id)
    log_audit(
        db=db, action="ADMIN_DEACTIVATE_USER",
        user_id=str(admin.id), username=admin.username,
        resource_type="user", resource_id=user_id,
        response_status=200,
    )
    return {"message": f"User {user_id} deactivated"}


# ── Audit Logs ─────────────────────────────────────────────────

@router.get(
    "/audit-logs",
    summary="View audit logs with optional filters (admin only)",
)
def get_audit_logs(
    action: Optional[str] = Query(None, description="e.g. AUTH_LOGIN, PREDICT"),
    username: Optional[str] = Query(None),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    skip: int = 0,
    limit: int = Query(100, le=500),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(AuditLog).order_by(desc(AuditLog.created_at))

    if action:
        stmt = stmt.where(AuditLog.action == action.upper())
    if username:
        stmt = stmt.where(AuditLog.username.ilike(f"%{username}%"))
    if start:
        stmt = stmt.where(AuditLog.created_at >= start)
    if end:
        stmt = stmt.where(AuditLog.created_at <= end)

    logs = db.scalars(stmt.offset(skip).limit(limit)).all()

    return [
        {
            "id": log.id,
            "username": log.username,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "ip_address": str(log.ip_address) if log.ip_address else None,
            "response_status": log.response_status,
            "duration_ms": log.duration_ms,
            "created_at": log.created_at,
        }
        for log in logs
    ]


# ── ML Model Management ────────────────────────────────────────

def _run_retraining():
    """
    Background retraining task.
    In Phase 5 this calls ml/train.py via subprocess.
    For now it logs that retraining was triggered.
    """
    from app.core.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("Model retraining triggered — implement ml/train.py in Phase 5")


@router.post(
    "/ml/retrain",
    summary="Trigger async ML model retraining (admin only)",
)
def trigger_retrain(
    background_tasks: BackgroundTasks,
    _: User = Depends(require_admin),
):
    """
    Kicks off model retraining in the background.
    Does not block the response — returns immediately.
    Check /admin/ml/status to see when the new model is available.
    """
    background_tasks.add_task(_run_retraining)
    return {"message": "Retraining queued", "status": "started"}


@router.get(
    "/ml/status",
    summary="Current model versions and last retrain info (admin only)",
)
def get_ml_status(_: User = Depends(require_admin)):
    """Returns what model is currently loaded and when it was last updated."""
    from app.core.config import settings
    from pathlib import Path
    import os

    model_path = Path(settings.MODEL_DIR) / f"{settings.ACTIVE_MODEL_NAME}.pkl"
    model_exists = model_path.exists()
    last_modified = None
    if model_exists:
        ts = os.path.getmtime(model_path)
        last_modified = datetime.fromtimestamp(ts).isoformat()

    return {
        "active_model": settings.ACTIVE_MODEL_NAME,
        "model_file_exists": model_exists,
        "last_modified": last_modified,
        "model_dir": settings.MODEL_DIR,
        "mode": "real" if model_exists else "heuristic_mock",
    }


# ── System Health ──────────────────────────────────────────────

@router.get(
    "/system/health",
    summary="Detailed system health check (admin only)",
)
def system_health(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    db_status = check_db_connection()

    # Count table row counts
    try:
        from sqlalchemy import text
        tables = ["users", "trains", "stations", "delay_records", "predictions", "anomalies"]
        counts = {}
        for table in tables:
            counts[table] = db.scalar(text(f"SELECT COUNT(*) FROM {table}")) or 0
    except Exception as exc:
        counts = {"error": str(exc)}

    return {
        "status": "healthy" if db_status["status"] == "healthy" else "degraded",
        "database": db_status,
        "row_counts": counts,
    }