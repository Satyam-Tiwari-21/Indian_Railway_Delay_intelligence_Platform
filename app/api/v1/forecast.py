# app/api/v1/forecast.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.models.db.user import User
import app.services.forecast_service as svc

router = APIRouter()


@router.get(
    "/zone/{zone_code}",
    summary="30-day delay forecast for a railway zone",
)
def get_zone_forecast(
    zone_code: str,
    days: int = Query(30, ge=7, le=90, description="Days to forecast ahead"),
    _: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Returns a day-by-day delay forecast for the given zone.
    Each entry: {date, predicted_avg_delay, lower_80, upper_80}

    Uses linear trend + Indian seasonality in Phase 2.
    Replaced by Prophet model in Phase 5.
    """
    try:
        return svc.get_zone_forecast(db, zone_code=zone_code, days=days)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/route/{train_number}",
    summary="14-day delay forecast for a specific train",
)
def get_route_forecast(
    train_number: str,
    days: int = Query(14, ge=3, le=30),
    _: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        return svc.get_route_forecast(db, train_number=train_number, days=days)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))