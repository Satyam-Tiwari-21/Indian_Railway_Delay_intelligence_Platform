# app/models/db/route.py

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, SmallInteger, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.db.train import Train
    from app.models.db.station import Station


class Route(Base):
    __tablename__ = "routes"
    __table_args__ = (
        UniqueConstraint("train_id", "stop_number", name="uq_route_train_stop"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    train_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("trains.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    station_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("stations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # 1 = origin, N = destination
    stop_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # NULL for origin station (no arrival), NULL for last stop (no departure)
    scheduled_arrival: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    scheduled_departure: Mapped[Optional[time]] = mapped_column(Time, nullable=True)

    # For overnight trains: 0 = day 1, 1 = day 2
    day_offset: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    # Distance from origin in km
    distance_from_origin: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Minutes the train halts at this station
    halt_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=2)

    # Relationships
    train: Mapped["Train"] = relationship("Train", back_populates="routes")
    station: Mapped["Station"] = relationship("Station", back_populates="routes")

    def __repr__(self) -> str:
        return (
            f"<Route train_id={self.train_id} "
            f"stop={self.stop_number} station_id={self.station_id}>"
        )

    @property
    def is_origin(self) -> bool:
        return self.stop_number == 1