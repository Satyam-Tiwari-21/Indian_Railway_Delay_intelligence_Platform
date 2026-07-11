# app/models/db/prediction.py

from __future__ import annotations
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.db.train import Train
    from app.models.db.station import Station
    from app.models.db.user import User


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    train_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trains.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    station_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    predicted_for_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    model_name: Mapped[str] = mapped_column(String(50), nullable=False)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)

    predicted_delay_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_lower: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_upper: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    class_probabilities: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    shap_values: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    input_features: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ← FIXED: UUID type to match users.id
    requested_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    inference_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    train: Mapped["Train"] = relationship("Train", back_populates="predictions")
    station: Mapped["Station"] = relationship("Station")
    requested_by_user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="predictions", foreign_keys=[requested_by]
    )

    def __repr__(self) -> str:
        return (
            f"<Prediction train_id={self.train_id} "
            f"date={self.predicted_for_date} "
            f"delay={self.predicted_delay_minutes:.1f}min>"
        )