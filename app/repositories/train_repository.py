# app/repositories/train_repository.py

from typing import Optional

from sqlalchemy import select, or_
from sqlalchemy.orm import Session, joinedload

from app.models.db.train import Train
from app.models.db.station import Station
from app.repositories.base_repository import BaseRepository


class TrainRepository(BaseRepository[Train]):

    def __init__(self, db: Session) -> None:
        super().__init__(Train, db)

    # ── Lookups ────────────────────────────────────────────────

    def get_by_number(self, train_number: str) -> Optional[Train]:
        """Primary lookup — train number is used in all API requests."""
        stmt = (
            select(Train)
            .options(
                joinedload(Train.origin_station),
                joinedload(Train.destination_station),
            )
            .where(Train.train_number == train_number)
            .where(Train.is_active == True)
        )
        return self.db.scalar(stmt)

    def get_by_number_or_404(self, train_number: str) -> Train:
        train = self.get_by_number(train_number)
        if not train:
            raise ValueError(f"Train {train_number!r} not found or is inactive")
        return train

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        zone: Optional[str] = None,
        limit: int = 20,
    ) -> list[Train]:
        """
        Search by train number or name — for autocomplete dropdowns in the dashboard.
        """
        stmt = (
            select(Train)
            .where(Train.is_active == True)
            .where(
                or_(
                    Train.train_number.ilike(f"%{query}%"),
                    Train.name.ilike(f"%{query}%"),
                )
            )
        )
        if category:
            stmt = stmt.where(Train.category == category)
        if zone:
            stmt = stmt.where(Train.zone == zone)

        stmt = stmt.order_by(Train.train_number).limit(limit)
        return list(self.db.scalars(stmt).all())

    def get_by_zone(self, zone: str, active_only: bool = True) -> list[Train]:
        stmt = select(Train).where(Train.zone == zone)
        if active_only:
            stmt = stmt.where(Train.is_active == True)
        return list(self.db.scalars(stmt).all())

    def get_by_category(self, category: str) -> list[Train]:
        stmt = (
            select(Train)
            .where(Train.category == category)
            .where(Train.is_active == True)
            .order_by(Train.train_number)
        )
        return list(self.db.scalars(stmt).all())

    def get_all_categories(self) -> list[str]:
        """Distinct categories — for filter dropdowns."""
        from sqlalchemy import distinct
        stmt = select(distinct(Train.category)).where(Train.is_active == True)
        return [row for row in self.db.scalars(stmt).all() if row]

    def get_all_zones(self) -> list[str]:
        """Distinct zones — for filter dropdowns."""
        from sqlalchemy import distinct
        stmt = select(distinct(Train.zone)).where(Train.is_active == True)
        return [row for row in self.db.scalars(stmt).all() if row]

    # ── Station lookup ─────────────────────────────────────────

    def get_station_by_code(self, station_code: str) -> Optional[Station]:
        stmt = select(Station).where(
            Station.station_code == station_code.upper()
        )
        return self.db.scalar(stmt)