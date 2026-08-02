# app/services/analytics_service.py
#
# Thin orchestration layer between the /api/v1/analytics/* routes and the
# repository layer. All heavy SQL aggregation already lives in
# DelayRecordRepository — this module's only job is to call it and shape
# the results into the Pydantic response schemas.
#
# Deliberately NOT doing raw queries here: if a new aggregation is needed,
# add it to DelayRecordRepository (or the relevant repository) and call it
# from here, so the query layer stays testable in isolation from FastAPI.

from datetime import date
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.db.train import Train
from app.models.db.station import Station
from app.models.db.anomaly import Anomaly
from app.models.db.delay_record import DelayRecord
from app.repositories.delay_record_repository import DelayRecordRepository
from app.models.schemas.analytics import (
    OverviewResponse,
    RouteStats,
    ZoneStats,
    StationStats,
    HeatmapPoint,
    SeasonalStats,
    TopRouteEntry,
)

logger = get_logger(__name__)


# ── Helpers ──────────────────────────────────────────────────────

def _full_data_range(db: Session) -> tuple[date, date]:
    """
    Min/max journey_date across all records — used to fill in date_range_start/
    end on the overview response when the caller didn't pass explicit filters.
    """
    row = db.execute(
        select(func.min(DelayRecord.journey_date), func.max(DelayRecord.journey_date))
    ).one()
    today = date.today()
    return (row[0] or today, row[1] or today)


# ── Overview ─────────────────────────────────────────────────────

def get_overview(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> OverviewResponse:
    repo = DelayRecordRepository(db)

    stats = repo.get_overview_stats(start_date=start_date, end_date=end_date)
    worst = repo.get_worst_zone(start_date=start_date, end_date=end_date)

    total_active_trains = db.scalar(
        select(func.count()).select_from(Train).where(Train.is_active == True)  # noqa: E712
    ) or 0
    total_stations = db.scalar(select(func.count()).select_from(Station)) or 0
    open_anomalies = db.scalar(
        select(func.count()).select_from(Anomaly).where(Anomaly.is_resolved == False)  # noqa: E712
    ) or 0

    range_start, range_end = start_date, end_date
    if range_start is None or range_end is None:
        full_start, full_end = _full_data_range(db)
        range_start = range_start or full_start
        range_end = range_end or full_end

    return OverviewResponse(
        total_active_trains=total_active_trains,
        total_stations=total_stations,
        avg_delay_minutes=stats["avg_delay_minutes"],
        otp_percentage=stats["otp_percentage"],
        total_records_analysed=stats["total_records"],
        worst_zone=worst["zone"] if worst else None,
        worst_zone_avg_delay=worst["avg_delay_minutes"] if worst else None,
        open_anomalies=open_anomalies,
        date_range_start=range_start,
        date_range_end=range_end,
    )


# ── Routes ───────────────────────────────────────────────────────

def get_route_stats(
    db: Session,
    zone: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 20,
    sort_by: str = "avg_delay_desc",
) -> list[RouteStats]:
    repo = DelayRecordRepository(db)
    rows = repo.get_route_stats(
        zone=zone, category=category,
        start_date=start_date, end_date=end_date,
        limit=limit, order_by=sort_by,
    )
    return [
        RouteStats(
            train_id=r["train_id"],
            train_number=r["train_number"],
            train_name=r["train_name"],
            category=r["category"],
            zone=r["zone"],
            origin_code=r["origin_code"],
            destination_code=r["destination_code"],
            avg_delay_minutes=float(r["avg_delay"] or 0),
            median_delay_minutes=float(r["median_delay"] or 0),
            otp_percentage=float(r["otp_percentage"] or 0),
            total_runs=r["total_runs"] or 0,
            severe_delay_count=int(r["severe_count"] or 0),
        )
        for r in rows
    ]


def _top_routes(
    db: Session,
    n: int,
    zone: Optional[str],
    category: Optional[str],
    order_by: str,
) -> list[TopRouteEntry]:
    repo = DelayRecordRepository(db)
    rows = repo.get_route_stats(zone=zone, category=category, limit=n, order_by=order_by)
    return [
        TopRouteEntry(
            rank=i + 1,
            train_number=r["train_number"],
            train_name=r["train_name"],
            origin_code=r["origin_code"],
            destination_code=r["destination_code"],
            avg_delay_minutes=float(r["avg_delay"] or 0),
            otp_percentage=float(r["otp_percentage"] or 0),
        )
        for i, r in enumerate(rows)
    ]


def get_top_delayed(
    db: Session, n: int = 20, zone: Optional[str] = None, category: Optional[str] = None
) -> list[TopRouteEntry]:
    return _top_routes(db, n=n, zone=zone, category=category, order_by="avg_delay_desc")


def get_top_punctual(
    db: Session, n: int = 20, zone: Optional[str] = None, category: Optional[str] = None
) -> list[TopRouteEntry]:
    return _top_routes(db, n=n, zone=zone, category=category, order_by="otp_asc")


# ── Zones ────────────────────────────────────────────────────────

def get_zone_stats(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> list[ZoneStats]:
    repo = DelayRecordRepository(db)
    rows = repo.get_zone_stats(start_date=start_date, end_date=end_date)
    return [
        ZoneStats(
            zone=r["zone"],
            avg_delay_minutes=float(r["avg_delay"] or 0),
            otp_percentage=float(r["otp_percentage"] or 0),
            total_records=r["total_records"] or 0,
            p90_delay_minutes=float(r["p90_delay"] or 0),
            severe_count=int(r["severe_count"] or 0),
        )
        for r in rows
    ]


# ── Seasonal ─────────────────────────────────────────────────────

def get_seasonal_stats(db: Session, year: Optional[int] = None) -> list[SeasonalStats]:
    repo = DelayRecordRepository(db)
    rows = repo.get_seasonal_stats(year=year)
    return [SeasonalStats(**r) for r in rows]


# ── Heatmap ──────────────────────────────────────────────────────

def get_heatmap(
    db: Session,
    metric: str = "avg_delay",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> list[HeatmapPoint]:
    repo = DelayRecordRepository(db)
    rows = repo.get_heatmap_data(metric=metric, start_date=start_date, end_date=end_date)
    return [
        HeatmapPoint(
            station_code=r["station_code"],
            station_name=r["station_name"],
            latitude=float(r["latitude"]),
            longitude=float(r["longitude"]),
            value=float(r["value"] or 0),
            total_trains=int(r["total_trains"] or 0),
        )
        for r in rows
        if r["latitude"] is not None and r["longitude"] is not None
    ]


# ── Stations ─────────────────────────────────────────────────────

def get_station_stats(
    db: Session,
    zone: Optional[str] = None,
    limit: int = 20,
) -> list[StationStats]:
    """
    Station congestion scoring. congestion_score is normalised 0-100 relative
    to the worst station *in the current result set* (simple min-max scaling —
    good enough for a dashboard ranking, not a calibrated cross-run metric).
    """
    repo = DelayRecordRepository(db)
    rows = repo.get_station_stats(zone=zone, limit=limit)
    if not rows:
        return []

    max_delay = max(float(r["avg_departure_delay"] or 0) for r in rows) or 1.0
    return [
        StationStats(
            station_code=r["station_code"],
            station_name=r["station_name"],
            zone=r["zone"],
            avg_departure_delay=float(r["avg_departure_delay"] or 0),
            total_train_passes=r["total_train_passes"] or 0,
            congestion_score=round(
                min(100.0, (float(r["avg_departure_delay"] or 0) / max_delay) * 100), 1
            ),
        )
        for r in rows
    ]
