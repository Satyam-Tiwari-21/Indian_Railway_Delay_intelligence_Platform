# app/api/v1/analytics.py

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.models.db.user import User
from app.models.schemas.analytics import (
    HeatmapPoint,
    OverviewResponse,
    RouteStats,
    SeasonalStats,
    StationStats,
    TopRouteEntry,
    ZoneStats,
)
import app.services.analytics_service as svc

router = APIRouter()


@router.get(
    "/overview",
    response_model=OverviewResponse,
    summary="Network-wide KPIs for the Home dashboard",
)
def get_overview(
    start_date: Optional[date] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    _: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return svc.get_overview(db, start_date=start_date, end_date=end_date)


@router.get(
    "/routes",
    response_model=list[RouteStats],
    summary="Per-route delay statistics",
)
def get_routes(
    zone: Optional[str] = Query(None, description="Filter by zone e.g. NR, SR, CR"),
    category: Optional[str] = Query(None, description="Filter by category e.g. Rajdhani, Express"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("avg_delay_desc", description="avg_delay_desc | otp_asc"),
    _: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return svc.get_route_stats(
        db, zone=zone, category=category,
        start_date=start_date, end_date=end_date,
        limit=limit, sort_by=sort_by,
    )


@router.get(
    "/zones",
    response_model=list[ZoneStats],
    summary="Zone-wise OTP and delay breakdown",
)
def get_zones(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return svc.get_zone_stats(db, start_date=start_date, end_date=end_date)


@router.get(
    "/seasonal",
    response_model=list[SeasonalStats],
    summary="Monthly delay pattern showing monsoon/fog season effects",
)
def get_seasonal(
    year: Optional[int] = Query(None, description="Filter by year e.g. 2024"),
    _: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return svc.get_seasonal_stats(db, year=year)


@router.get(
    "/heatmap",
    response_model=list[HeatmapPoint],
    summary="Station coordinates + delay metric for map heatmap",
)
def get_heatmap(
    metric: str = Query("avg_delay", description="avg_delay | severe_count"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return svc.get_heatmap(db, metric=metric, start_date=start_date, end_date=end_date)


@router.get(
    "/stations",
    response_model=list[StationStats],
    summary="Station congestion scores",
)
def get_stations(
    zone: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    _: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return svc.get_station_stats(db, zone=zone, limit=limit)


@router.get(
    "/top-delayed",
    response_model=list[TopRouteEntry],
    summary="Top N most-delayed routes",
)
def get_top_delayed(
    n: int = Query(20, ge=1, le=50),
    zone: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    _: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return svc.get_top_delayed(db, n=n, zone=zone, category=category)


@router.get(
    "/top-punctual",
    response_model=list[TopRouteEntry],
    summary="Top N most-reliable routes",
)
def get_top_punctual(
    n: int = Query(20, ge=1, le=50),
    zone: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    _: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return svc.get_top_punctual(db, n=n, zone=zone, category=category)


@router.get(
    "/categories",
    summary="List all distinct train categories in the database",
)
def get_categories(
    _: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    from app.repositories.train_repository import TrainRepository
    return {"categories": TrainRepository(db).get_all_categories()}


@router.get(
    "/zones-list",
    summary="List all distinct zone codes in the database",
)
def get_zones_list(
    _: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    from app.repositories.train_repository import TrainRepository
    return {"zones": TrainRepository(db).get_all_zones()}