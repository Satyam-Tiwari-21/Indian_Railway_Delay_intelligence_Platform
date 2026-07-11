# app/models/db/anomaly.py

from __future__ import annotations
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    ARRAY, BigInteger, Boolean, Date, DateTime,
    Float, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.db.train import Train
    from app.models.db.station import Station
    from app.models.db.delay_record import DelayRecord
    from app.models.db.user import User


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

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

    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False)
    z_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    anomaly_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    affected_trains: Mapped[Optional[list]] = mapped_column(ARRAY(Integer), nullable=True)

    is_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ← FIXED: UUID type to match users.id
    resolved_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    train: Mapped[Optional["Train"]] = relationship("Train", back_populates="anomalies")
    station: Mapped[Optional["Station"]] = relationship("Station")
    delay_record: Mapped[Optional["DelayRecord"]] = relationship(
        "DelayRecord", back_populates="anomalies"
    )
    resolver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[resolved_by])

    def __repr__(self) -> str:
        return (
            f"<Anomaly id={self.id} train_id={self.train_id} "
            f"severity={self.severity} resolved={self.is_resolved}>"
        )