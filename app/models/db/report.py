# app/models/db/report.py

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.db.user import User


REPORT_TYPES = [
    "EDA_SUMMARY",        # Exploratory data analysis summary
    "PREDICTION_BATCH",   # Batch prediction results
    "ANOMALY_REPORT",     # Anomaly detection summary
    "EXECUTIVE_MONTHLY",  # Monthly executive summary
]


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    report_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Filters used to generate this report
    # {"zone": "NR", "month": "2024-08", "category": "Express"}
    parameters: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Path to the generated file on disk / object storage
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_format: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # PDF | CSV
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    generated_by: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Reports auto-expire — cleaned up by a background job
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ──────────────────────────────────────────
    generator: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<Report id={self.id[:8]}... type={self.report_type!r}>"

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at.replace(tzinfo=None)