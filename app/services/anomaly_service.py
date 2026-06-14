# app/services/anomaly_service.py

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from app.core.logging_config import get_logger
from app.models.db.anomaly import Anomaly
from app.models.db.train import Train
from app.models.db.station import Station
from app.models.schemas.anomaly import AnomalyFeed, AnomalyOut, AnomalyStats
from app.services.auth_service import log_audit

logger = get_logger(__name__)


def _to_out(anomaly: Anomaly) -> AnomalyOut:
    """Convert ORM Anomaly to Pydantic AnomalyOut."""
    return AnomalyOut(
        id=anomaly.id,
        train_number=anomaly.train.train_number if anomaly.train else None,
        train_name=anomaly.train.name if anomaly.train else None,
        station_code=anomaly.station.station_code if anomaly.station else None,
        anomaly_date=anomaly.anomaly_date,
        anomaly_score=anomaly.anomaly_score,
        z_score=anomaly.z_score,
        anomaly_type=anomaly.anomaly_type,
        severity=anomaly.severity,
        explanation=anomaly.explanation,
        affected_train_count=len(anomaly.affected_trains or []),
        is_resolved=anomaly.is_resolved,
        resolved_at=anomaly.resolved_at,
        resolution_note=anomaly.resolution_note,
        created_at=anomaly.created_at,
    )


def _base_query(db: Session):
    """Base query with eager-loaded relations."""
    return (
        select(Anomaly)
        .options(
            joinedload(Anomaly.train),
            joinedload(Anomaly.station),
        )
    )


# ── Read ───────────────────────────────────────────────────────

def get_feed(
    db: Session,
    severity: Optional[str] = None,
    resolved: bool = False,
    limit: int = 50,
) -> AnomalyFeed:
    """Anomaly feed for the dashboard alert panel, newest first."""
    stmt = (
        _base_query(db)
        .where(Anomaly.is_resolved == resolved)
        .order_by(desc(Anomaly.created_at))
        .limit(limit)
    )
    if severity:
        stmt = stmt.where(Anomaly.severity == severity.upper())

    anomalies = list(db.scalars(stmt).all())

    # Severity counts for the summary bar
    counts_stmt = (
        select(Anomaly.severity, func.count().label("cnt"))
        .where(Anomaly.is_resolved == False)
        .group_by(Anomaly.severity)
    )
    counts = {row.severity: row.cnt for row in db.execute(counts_stmt).all()}

    return AnomalyFeed(
        total=len(anomalies),
        critical_count=counts.get("CRITICAL", 0),
        high_count=counts.get("HIGH", 0),
        medium_count=counts.get("MEDIUM", 0),
        anomalies=[_to_out(a) for a in anomalies],
    )


def get_by_id(db: Session, anomaly_id: int) -> Anomaly:
    """Fetch a single anomaly with all relations. Raises ValueError if not found."""
    stmt = _base_query(db).where(Anomaly.id == anomaly_id)
    anomaly = db.scalar(stmt)
    if anomaly is None:
        raise ValueError(f"Anomaly {anomaly_id} not found")
    return anomaly


def get_stats(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> AnomalyStats:
    """Anomaly counts grouped by type and severity for the stats panel."""
    stmt = select(
        Anomaly.anomaly_type,
        Anomaly.severity,
        func.count().label("cnt"),
    )
    if start_date:
        stmt = stmt.where(Anomaly.anomaly_date >= start_date)
    if end_date:
        stmt = stmt.where(Anomaly.anomaly_date <= end_date)

    rows = db.execute(stmt.group_by(Anomaly.anomaly_type, Anomaly.severity)).all()

    by_type: dict[str, int] = {}
    by_sev: dict[str, int] = {}
    total = 0
    for row in rows:
        total += row.cnt
        by_type[row.anomaly_type or "UNKNOWN"] = (
            by_type.get(row.anomaly_type or "UNKNOWN", 0) + row.cnt
        )
        by_sev[row.severity or "UNKNOWN"] = (
            by_sev.get(row.severity or "UNKNOWN", 0) + row.cnt
        )

    resolved_count = db.scalar(
        select(func.count()).select_from(Anomaly).where(Anomaly.is_resolved == True)
    ) or 0
    resolution_rate = round(resolved_count / total * 100, 1) if total > 0 else 0.0

    from datetime import timedelta
    return AnomalyStats(
        date_range_start=start_date or (date.today() - timedelta(days=30)),
        date_range_end=end_date or date.today(),
        total_anomalies=total,
        by_type=by_type,
        by_severity=by_sev,
        resolution_rate=resolution_rate,
    )


# ── Write ──────────────────────────────────────────────────────

def resolve_anomaly(
    db: Session,
    anomaly_id: int,
    user_id: str,
    note: str,
) -> AnomalyOut:
    """Mark an anomaly as resolved. Raises ValueError if already resolved."""
    anomaly = get_by_id(db, anomaly_id)

    if anomaly.is_resolved:
        raise ValueError(f"Anomaly {anomaly_id} is already resolved")

    anomaly.is_resolved = True
    anomaly.resolved_by = user_id
    anomaly.resolved_at = datetime.now(timezone.utc)
    anomaly.resolution_note = note
    db.flush()

    log_audit(
        db=db,
        action="RESOLVE_ANOMALY",
        user_id=user_id,
        resource_type="anomaly",
        resource_id=str(anomaly_id),
        response_status=200,
    )

    logger.info("Anomaly resolved", anomaly_id=anomaly_id, user_id=user_id)
    return _to_out(anomaly)