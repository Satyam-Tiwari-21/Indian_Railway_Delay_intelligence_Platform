# app/models/db/delay_record.py
# Main fact table — one row per train stop per day
# This is the largest table: 500K–5M rows after full historical load

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.db.train import Train
    from app.models.db.station import Station
    from app.models.db.anomaly import Anomaly


# Reason codes for delays — from Indian Railways operational taxonomy
REASON_CODES = [
    "FOG",               # Dense fog — Northern Railway, Dec–Jan
    "FLOOD",             # Monsoon flooding on tracks
    "SIGNAL_FAIL",       # Signalling equipment failure
    "ACCIDENT",          # Collision or derailment
    "LATE_RUNNING",      # Accumulated delay from earlier stations
    "ENGINEERING_WORK",  # Planned track maintenance
    "CREW_CHANGE",       # Loco pilot or guard not available
    "FREIGHT_CLEARANCE", # Goods train blocking the line
    "MISC",              # Everything else
]

WEATHER_CONDITIONS = [
    "CLEAR",
    "LIGHT_RAIN",
    "HEAVY_RAIN",
    "FOG",
    "DENSE_FOG",
    "CYCLONE",
    "HEATWAVE",
]


class DelayRecord(Base):
    __tablename__ = "delay_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    train_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trains.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    station_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stations.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    journey_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Denormalised from routes table for faster analytics queries
    stop_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Arrival data
    scheduled_arrival: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_arrival: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Negative = arrived early. Positive = arrived late (delay).
    arrival_delay_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Departure data
    scheduled_departure: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_departure: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    departure_delay_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    reason_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reason_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    weather_condition: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # 'historical' = loaded from CSV; 'ntes_live' = scraped from NTES
    data_source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="historical"
    )
    is_cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────
    train: Mapped["Train"] = relationship("Train", back_populates="delay_records")
    station: Mapped["Station"] = relationship("Station", back_populates="delay_records")
    anomalies: Mapped[list["Anomaly"]] = relationship(
        "Anomaly", back_populates="delay_record"
    )

    def __repr__(self) -> str:
        return (
            f"<DelayRecord train_id={self.train_id} "
            f"station_id={self.station_id} date={self.journey_date} "
            f"delay={self.arrival_delay_minutes}min>"
        )

    @property
    def is_on_time(self) -> bool:
        return (self.arrival_delay_minutes or 0) <= 5

    @property
    def delay_class(self) -> str:
        """Classify delay into operational categories."""
        minutes = self.arrival_delay_minutes or 0
        if minutes <= 5:
            return "ON_TIME"
        if minutes <= 30:
            return "SLIGHT"
        if minutes <= 120:
            return "MODERATE"
        return "SEVERE"