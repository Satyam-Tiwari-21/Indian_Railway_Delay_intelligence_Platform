# app/repositories/prediction_repository.py

from datetime import date
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.orm import Session, joinedload

from app.models.db.prediction import Prediction
from app.models.db.train import Train
from app.models.db.station import Station
from app.repositories.base_repository import BaseRepository


class PredictionRepository(BaseRepository[Prediction]):

    def __init__(self, db: Session) -> None:
        super().__init__(Prediction, db)

    def store(self, prediction_data: dict) -> Prediction:
        """Store a new prediction and return it with id populated."""
        return self.create(prediction_data)

    def get_user_history(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Prediction]:
        """All predictions made by a specific user, newest first."""
        stmt = (
            select(Prediction)
            .options(
                joinedload(Prediction.train),
                joinedload(Prediction.station),
            )
            .where(Prediction.requested_by == user_id)
            .order_by(desc(Prediction.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def get_by_id_with_relations(self, prediction_id: int) -> Optional[Prediction]:
        """Get a prediction with train + station eagerly loaded."""
        stmt = (
            select(Prediction)
            .options(
                joinedload(Prediction.train).joinedload(Train.origin_station),
                joinedload(Prediction.station),
            )
            .where(Prediction.id == prediction_id)
        )
        return self.db.scalar(stmt)

    def get_by_train_and_date(
        self,
        train_id: int,
        journey_date: date,
        station_id: Optional[int] = None,
    ) -> Optional[Prediction]:
        """
        Check if a prediction already exists for this train + date.
        Used to avoid re-running the model for duplicate requests.
        """
        stmt = (
            select(Prediction)
            .where(Prediction.train_id == train_id)
            .where(Prediction.predicted_for_date == journey_date)
            .order_by(desc(Prediction.created_at))
            .limit(1)
        )
        if station_id:
            stmt = stmt.where(Prediction.station_id == station_id)
        return self.db.scalar(stmt)

    def get_recent(self, limit: int = 100) -> list[Prediction]:
        """Most recent predictions across all users — for admin monitoring."""
        stmt = (
            select(Prediction)
            .options(joinedload(Prediction.train))
            .order_by(desc(Prediction.created_at))
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())