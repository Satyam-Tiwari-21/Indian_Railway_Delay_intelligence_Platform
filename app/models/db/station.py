# app/models/db/station.py

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.db.train import Train
    from app.models.db.route import Route
    from app.models.db.delay_record import DelayRecord


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_code: Mapped[str] = mapped_column(
        String(10), unique=True, nullable=False, index=True
        # Examples: 'NDLS' (New Delhi), 'HWH' (Howrah), 'MAS' (Chennai Central)
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Railway zone codes: NR, SR, CR, ER, WR, NER, ECR, SCR, SER, NCR, NWR, WCR, NFR, ECOR, SWR, SECR, KR, Metro
    zone: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, index=True)

    # GPS coordinates — used for heatmap visualizations
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)

    # Elevation in meters — higher = more fog risk in winter
    elevation_m: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Junction = major interchange point (multiple lines cross here)
    is_junction: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Approximate number of trains passing through per day — used for congestion scoring
    avg_daily_trains: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────
    origin_trains: Mapped[list["Train"]] = relationship(
        "Train", foreign_keys="Train.origin_station_id", back_populates="origin_station"
    )
    destination_trains: Mapped[list["Train"]] = relationship(
        "Train", foreign_keys="Train.destination_station_id", back_populates="destination_station"
    )
    routes: Mapped[list["Route"]] = relationship("Route", back_populates="station")
    delay_records: Mapped[list["DelayRecord"]] = relationship(
        "DelayRecord", back_populates="station"
    )

    def __repr__(self) -> str:
        return f"<Station {self.station_code!r} — {self.name!r}>"