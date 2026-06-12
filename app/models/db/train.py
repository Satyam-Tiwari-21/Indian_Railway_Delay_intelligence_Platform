# app/models/db/train.py

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.db.station import Station
    from app.models.db.route import Route
    from app.models.db.delay_record import DelayRecord
    from app.models.db.prediction import Prediction
    from app.models.db.anomaly import Anomaly


# Valid train categories in Indian Railways
TRAIN_CATEGORIES = [
    "Rajdhani",   # Premium — fastest, fully air-conditioned
    "Shatabdi",   # Day-time intercity premium
    "Duronto",    # Non-stop long-distance
    "Superfast",  # > 55 km/h average
    "Mail",       # Overnight mail + passenger
    "Express",    # Stops at major stations
    "Passenger",  # Stops at all stations — slowest, most delays
    "MEMU",       # Mainline Electric Multiple Unit (suburban)
    "EMU",        # Electric Multiple Unit (metro-area)
    "Goods",      # Freight — causes delays to passenger trains
]


class Train(Base):
    __tablename__ = "trains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 5-digit train number: '12301' = Howrah Rajdhani
    train_number: Mapped[str] = mapped_column(
        String(10), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # e.g., 'Rajdhani', 'Express', 'Passenger'
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    origin_station_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stations.id", ondelete="RESTRICT"), nullable=False
    )
    destination_station_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stations.id", ondelete="RESTRICT"), nullable=False
    )

    # Operating zone (matches the zone that manages this train)
    zone: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, index=True)

    total_stops: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    distance_km: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # e.g., 'Daily' or 'Mon,Wed,Fri'
    run_days: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────
    origin_station: Mapped["Station"] = relationship(
        "Station", foreign_keys=[origin_station_id], back_populates="origin_trains"
    )
    destination_station: Mapped["Station"] = relationship(
        "Station", foreign_keys=[destination_station_id], back_populates="destination_trains"
    )
    routes: Mapped[list["Route"]] = relationship(
        "Route", back_populates="train", cascade="all, delete-orphan"
    )
    delay_records: Mapped[list["DelayRecord"]] = relationship(
        "DelayRecord", back_populates="train"
    )
    predictions: Mapped[list["Prediction"]] = relationship(
        "Prediction", back_populates="train"
    )
    anomalies: Mapped[list["Anomaly"]] = relationship(
        "Anomaly", back_populates="train"
    )

    def __repr__(self) -> str:
        return f"<Train {self.train_number!r} — {self.name!r} ({self.category})>"

    @property
    def is_premium(self) -> bool:
        """Rajdhani, Shatabdi, Duronto — lowest delay tolerance."""
        return self.category in ("Rajdhani", "Shatabdi", "Duronto")

    @property
    def is_long_distance(self) -> bool:
        return (self.distance_km or 0) > 1000