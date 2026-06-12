# app/repositories/base_repository.py
# Generic CRUD operations — every repository inherits from this.
# No business logic here — only raw database access.

from typing import Generic, TypeVar, Type, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository providing CRUD for any SQLAlchemy model.

    Usage:
        class TrainRepository(BaseRepository[Train]):
            def __init__(self, db: Session):
                super().__init__(Train, db)
    """

    def __init__(self, model: Type[ModelType], db: Session) -> None:
        self.model = model
        self.db = db

    # ── READ ───────────────────────────────────────────────────

    def get(self, id: Any) -> Optional[ModelType]:
        """Get a single record by primary key. Returns None if not found."""
        return self.db.get(self.model, id)

    def get_or_404(self, id: Any) -> ModelType:
        """Get by PK — raises ValueError if not found (caller converts to HTTP 404)."""
        obj = self.get(id)
        if obj is None:
            raise ValueError(f"{self.model.__name__} with id={id!r} not found")
        return obj

    def get_multi(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ModelType]:
        """Paginated list of all records."""
        stmt = select(self.model).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def count(self) -> int:
        """Total row count for this model."""
        stmt = select(func.count()).select_from(self.model)
        return self.db.scalar(stmt) or 0

    def exists(self, id: Any) -> bool:
        return self.get(id) is not None

    # ── WRITE ──────────────────────────────────────────────────

    def create(self, obj_in: dict) -> ModelType:
        """
        Create a new record.
        obj_in: dict of column values e.g. {"name": "Howrah Rajdhani", "category": "Rajdhani"}
        Returns the created object (already flushed, id is available).
        """
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        self.db.flush()      # Get the DB-generated ID without committing
        self.db.refresh(db_obj)
        return db_obj

    def update(self, db_obj: ModelType, updates: dict) -> ModelType:
        """
        Update an existing record with a dict of changes.
        Only updates keys present in `updates` — leaves other fields unchanged.
        """
        for field, value in updates.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        self.db.flush()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: ModelType) -> None:
        """Hard delete. For soft-delete models use update(is_active=False)."""
        self.db.delete(db_obj)
        self.db.flush()

    def bulk_create(self, objects: list[dict]) -> int:
        """
        Bulk insert — much faster than calling create() in a loop.
        Returns the number of rows inserted.
        """
        if not objects:
            return 0
        self.db.bulk_insert_mappings(self.model, objects)
        self.db.flush()
        return len(objects)