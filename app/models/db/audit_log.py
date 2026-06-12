# app/models/db/audit_log.py
# Every user action is logged here — required for RBAC compliance

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.db.user import User


# All valid audit action codes
AUDIT_ACTIONS = [
    "AUTH_LOGIN",
    "AUTH_LOGIN_FAIL",
    "AUTH_LOGOUT",
    "AUTH_REFRESH",
    "PREDICT",
    "BATCH_PREDICT",
    "EXPORT_CSV",
    "EXPORT_PDF",
    "RESOLVE_ANOMALY",
    "ADMIN_CREATE_USER",
    "ADMIN_UPDATE_USER",
    "ADMIN_DEACTIVATE_USER",
    "MODEL_RETRAIN_TRIGGER",
    "REPORT_GENERATE",
    "REPORT_DOWNLOAD",
]


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    user_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    # Denormalised — user may be deleted later but we keep the log
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # What happened — one of AUDIT_ACTIONS
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # What resource was affected
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # prediction | report | user | model
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Network info — for security monitoring
    ip_address: Mapped[Optional[str]] = mapped_column(INET, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Sanitised request body — never include passwords or tokens
    request_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # HTTP response status (200, 403, 422, 500 etc.)
    response_status: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)

    # How long the request took — useful for identifying slow endpoints
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # ── Relationships ──────────────────────────────────────────
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} "
            f"user={self.username!r} "
            f"action={self.action!r} "
            f"status={self.response_status}>"
        )