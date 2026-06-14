# app/services/forecast_service.py
# Zone and route-level delay forecasts.
# Uses linear trend extrapolation from historical data now (Phase 2).
# In Phase 5, Prophet model replaces _trend_forecast() automatically.

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.db.delay_record import DelayRecord
from app.models.db.train import Train

logger = get_logger(__name__)

# Indian Railways seasonal multipliers — used to adjust trend forecast
_SEASONAL = {
    1: 1.45, 2: 1.10, 3: 1.00, 4: 1.05,
    5: 1.10, 6: 1.40, 7: 1.80, 8: 1.75,
    9: 1.50, 10: 1.10, 11: 1.05, 12: 1.40,
}

ZONE_CODES = [
    "NR", "SR", "CR", "ER", "WR",
    "NER", "ECR", "SCR", "SER", "NCR",
    "NWR", "WCR", "NFR", "ECOR", "SWR", "SECR",
]


def _get_zone_history(db: Session, zone: str, days: int = 90) -> list[dict]:
    """Fetch last N days of daily avg delay for a zone."""
    cutoff = date.today() - timedelta(days=days)
    rows = db.execute(
        select(
            DelayRecord.journey_date.label("dt"),
            func.round(func.avg(DelayRecord.arrival_delay_minutes), 1).label("avg_delay"),
        )
        .join(Train, DelayRecord.train_id == Train.id)
        .where(Train.zone == zone)
        .where(DelayRecord.journey_date >= cutoff)
        .where(DelayRecord.actual_arrival.is_not(None))
        .group_by(DelayRecord.journey_date)
        .order_by(DelayRecord.journey_date)
    ).all()
    return [{"date": r.dt, "avg_delay": float(r.avg_delay or 0)} for r in rows]


def _trend_forecast(history: list[dict], days_ahead: int) -> list[dict]:
    """
    Simple linear trend + seasonal adjustment.
    Replaced by Prophet in Phase 5 — same output format, better accuracy.
    """
    if not history:
        # No data — return flat forecast at network average
        base = 20.0
        return [
            {
                "date": date.today() + timedelta(days=i + 1),
                "predicted_avg_delay": round(base * _SEASONAL.get((date.today() + timedelta(days=i + 1)).month, 1.0), 1),
                "lower_80": round(base * 0.7, 1),
                "upper_80": round(base * 1.3, 1),
            }
            for i in range(days_ahead)
        ]

    values = [h["avg_delay"] for h in history]
    n = len(values)
    mean_y = sum(values) / n
    mean_x = (n - 1) / 2

    # Linear regression slope
    num = sum((i - mean_x) * (v - mean_y) for i, v in enumerate(values))
    den = sum((i - mean_x) ** 2 for i in range(n)) or 1
    slope = num / den

    last_val = values[-1]
    results = []
    for i in range(1, days_ahead + 1):
        forecast_date = date.today() + timedelta(days=i)
        trend_val = last_val + slope * i
        seasonal = _SEASONAL.get(forecast_date.month, 1.0)
        predicted = max(0.0, round(trend_val * seasonal, 1))
        ci_width = predicted * 0.25
        results.append({
            "date": forecast_date,
            "predicted_avg_delay": predicted,
            "lower_80": round(max(0.0, predicted - ci_width), 1),
            "upper_80": round(predicted + ci_width, 1),
        })
    return results


# ── Public API ─────────────────────────────────────────────────

def get_zone_forecast(
    db: Session,
    zone_code: str,
    days: int = 30,
) -> list[dict]:
    """
    30-day ahead delay forecast for a specific railway zone.
    Returned as a list of {date, predicted_avg_delay, lower_80, upper_80}.
    """
    zone_code = zone_code.upper()
    if zone_code not in ZONE_CODES:
        raise ValueError(
            f"Zone '{zone_code}' not recognised. "
            f"Valid zones: {', '.join(ZONE_CODES)}"
        )

    history = _get_zone_history(db, zone_code)
    forecast = _trend_forecast(history, days_ahead=min(days, 90))

    logger.info(
        "Zone forecast generated",
        zone=zone_code,
        history_days=len(history),
        forecast_days=len(forecast),
    )
    return forecast


def get_route_forecast(
    db: Session,
    train_number: str,
    days: int = 14,
) -> list[dict]:
    """14-day ahead delay forecast for a specific train route."""
    from app.repositories.train_repository import TrainRepository

    train = TrainRepository(db).get_by_number_or_404(train_number)
    cutoff = date.today() - timedelta(days=90)

    rows = db.execute(
        select(
            DelayRecord.journey_date.label("dt"),
            func.round(func.avg(DelayRecord.arrival_delay_minutes), 1).label("avg_delay"),
        )
        .where(DelayRecord.train_id == train.id)
        .where(DelayRecord.journey_date >= cutoff)
        .where(DelayRecord.actual_arrival.is_not(None))
        .group_by(DelayRecord.journey_date)
        .order_by(DelayRecord.journey_date)
    ).all()

    history = [{"date": r.dt, "avg_delay": float(r.avg_delay or 0)} for r in rows]
    return _trend_forecast(history, days_ahead=min(days, 30))