# app/api/v1/anomalies.py

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.models.db.user import User
from app.models.schemas.anomaly import AnomalyFeed, AnomalyOut, AnomalyStats, ResolveRequest
import app.services.anomaly_service as svc

router = APIRouter()


@router.get(
    "/feed",
    response_model=AnomalyFeed,
    summary="Live anomaly feed for the alert dashboard",
)
def get_feed(
    severity: Optional[str] = Query(None, description="CRITICAL | HIGH | MEDIUM | LOW"),
    resolved: bool = Query(False, description="Include resolved anomalies"),
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return svc.get_feed(db, severity=severity, resolved=resolved, limit=limit)


@router.get(
    "/stats",
    response_model=AnomalyStats,
    summary="Anomaly counts grouped by type and severity",
)
def get_stats(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return svc.get_stats(db, start_date=start_date, end_date=end_date)


@router.get(
    "/{anomaly_id}",
    response_model=AnomalyOut,
    summary="Get a specific anomaly by ID",
)
def get_anomaly(
    anomaly_id: int,
    _: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        return svc._to_out(svc.get_by_id(db, anomaly_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put(
    "/{anomaly_id}/resolve",
    response_model=AnomalyOut,
    summary="Mark an anomaly as resolved",
)
def resolve_anomaly(
    anomaly_id: int,
    body: ResolveRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Marks the anomaly as resolved with a note.
    Requires at least officer role — viewers cannot resolve anomalies.
    """
    if not user.has_permission("can_predict"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Officer role or above required to resolve anomalies",
        )
    try:
        return svc.resolve_anomaly(db, anomaly_id, str(user.id), body.resolution_note)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))