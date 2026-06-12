# app/repositories/user_repository.py

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.models.db.user import User, Role
from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):

    def __init__(self, db: Session) -> None:
        super().__init__(User, db)

    # ── Lookups ────────────────────────────────────────────────

    def get_by_email(self, email: str) -> Optional[User]:
        stmt = (
            select(User)
            .options(joinedload(User.role))  # Load role in same query
            .where(User.email == email.lower())
        )
        return self.db.scalar(stmt)

    def get_by_username(self, username: str) -> Optional[User]:
        stmt = (
            select(User)
            .options(joinedload(User.role))
            .where(User.username == username.lower())
        )
        return self.db.scalar(stmt)

    def get_with_role(self, user_id: str) -> Optional[User]:
        """Get user with role eagerly loaded — avoids N+1 on permission checks."""
        stmt = (
            select(User)
            .options(joinedload(User.role))
            .where(User.id == user_id)
        )
        return self.db.scalar(stmt)

    def get_all_active(self, skip: int = 0, limit: int = 100) -> list[User]:
        stmt = (
            select(User)
            .options(joinedload(User.role))
            .where(User.is_active == True)
            .order_by(User.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    # ── Auth ───────────────────────────────────────────────────

    def record_login(self, user_id: str) -> None:
        """Update last_login_at timestamp after successful authentication."""
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(last_login_at=datetime.now(timezone.utc))
        )
        self.db.execute(stmt)
        self.db.flush()

    def deactivate(self, user_id: str) -> None:
        """Soft delete — never hard-delete users (audit trail must remain)."""
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(is_active=False)
        )
        self.db.execute(stmt)
        self.db.flush()

    # ── Roles ──────────────────────────────────────────────────

    def get_role_by_name(self, name: str) -> Optional[Role]:
        stmt = select(Role).where(Role.name == name)
        return self.db.scalar(stmt)

    def get_all_roles(self) -> list[Role]:
        return list(self.db.scalars(select(Role)).all())