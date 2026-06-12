# app/models/db/anomaly.py

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.db.train import Train
    from app.models.db.station import Station
    from app.models.db.delay_record import DelayRecord
    from app.models.db.user import User


ANOMALY_TYPES = [
    "EXTREME_DELAY",        # Single train delayed far beyond its historical norm
    "ROUTE_DISRUPTION",     # Multiple trains on a route all delayed
    "CASCADING_DELAY",      # One late train causes downstream trains to be late
    "EARLY_DEPARTURE",      # Train left significantly earlier than scheduled
    "CANCELLATION_PATTERN", # Repeated cancellations on a route
]

SEVERITY_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # The delay record that triggered this anomaly (if applicable)
    delay_record_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("delay_records.id", ondelete="SET NULL"), nullable=True
    )
    train_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("trains.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    station_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("stations.id", ondelete="SET NULL"), nullable=True
    )
    anomaly_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Isolation Forest score — more negative = more anomalous
    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False)

    # How many standard deviations above the route-month historical mean
    z_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    anomaly_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)

    # Human-readable explanation of why this is anomalous
    # e.g., "Train 12301 is 4.2 std devs above July NR zone average"
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # IDs of downstream trains affected by this disruption
    affected_trains: Mapped[Optional[list]] = mapped_column(
        ARRAY(Integer), nullable=True
    )

    is_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_by: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────
    train: Mapped[Optional["Train"]] = relationship("Train", back_populates="anomalies")
    station: Mapped[Optional["Station"]] = relationship("Station")
    delay_record: Mapped[Optional["DelayRecord"]] = relationship(
        "DelayRecord", back_populates="anomalies"
    )
    resolver: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[resolved_by]
    )

    def __repr__(self) -> str:
        return (
            f"<Anomaly id={self.id} "
            f"train_id={self.train_id} "
            f"date={self.anomaly_date} "
            f"severity={self.severity} "
            f"resolved={self.is_resolved}>"
        )