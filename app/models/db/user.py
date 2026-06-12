# app/models/db/user.py

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.db.prediction import Prediction
    from app.models.db.audit_log import AuditLog


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    # admin | analyst | officer | viewer
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    permissions: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: {},
        # Example: {"can_predict": true, "can_export": true, "can_admin": false}
    )

    # ── Relationships ──────────────────────────────────────────
    users: Mapped[list["User"]] = relationship("User", back_populates="role")

    def __repr__(self) -> str:
        return f"<Role id={self.id} name={self.name!r}>"

    def has_permission(self, permission: str) -> bool:
        return bool(self.permissions.get(permission, False))


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    username: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # NULL = access to all zones; 'NR' = Northern Railway only
    zone_access: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ──────────────────────────────────────────
    role: Mapped["Role"] = relationship("Role", back_populates="users")
    predictions: Mapped[list["Prediction"]] = relationship(
        "Prediction", back_populates="requested_by_user", foreign_keys="Prediction.requested_by"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id[:8]}... username={self.username!r}>"

    def has_permission(self, permission: str) -> bool:
        """Check if this user's role has a specific permission."""
        if not self.role:
            return False
        return self.role.has_permission(permission)

    def can_access_zone(self, zone: str) -> bool:
        """None = all zones allowed; specific value = only that zone."""
        if self.zone_access is None:
            return True
        return self.zone_access == zone