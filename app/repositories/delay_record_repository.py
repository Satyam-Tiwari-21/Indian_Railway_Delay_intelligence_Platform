# app/repositories/delay_record_repository.py
# The most query-heavy repository — all analytics aggregations live here.

from datetime import date
from typing import Optional

from sqlalchemy import and_, case, func, select, text
from sqlalchemy.orm import Session

from app.models.db.delay_record import DelayRecord
from app.models.db.train import Train
from app.models.db.station import Station
from app.repositories.base_repository import BaseRepository


class DelayRecordRepository(BaseRepository[DelayRecord]):

    def __init__(self, db: Session) -> None:
        super().__init__(DelayRecord, db)

    # ── Overview KPIs ──────────────────────────────────────────

    def get_overview_stats(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """
        Network-wide KPIs for the Home dashboard.
        Returns avg_delay, otp_rate, total_records, worst_zone.
        """
        stmt = (
            select(
                func.count().label("total_records"),
                func.round(func.avg(DelayRecord.arrival_delay_minutes), 2).label("avg_delay"),
                func.round(
                    func.sum(
                        case(
                            (DelayRecord.arrival_delay_minutes <= 5, 1),
                            else_=0,
                        )
                    ).cast(Float) / func.count() * 100,
                    2,
                ).label("otp_percentage"),
            )
            .where(DelayRecord.actual_arrival.is_not(None))
            .where(DelayRecord.is_cancelled == False)
        )
        stmt = self._apply_date_filter(stmt, start_date, end_date)
        row = self.db.execute(stmt).one()
        return {
            "total_records": row.total_records or 0,
            "avg_delay_minutes": float(row.avg_delay or 0),
            "otp_percentage": float(row.otp_percentage or 0),
        }

    def get_worst_zone(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Optional[dict]:
        """Zone with the highest average delay."""
        stmt = (
            select(
                Train.zone,
                func.round(func.avg(DelayRecord.arrival_delay_minutes), 2).label("avg_delay"),
            )
            .join(Train, DelayRecord.train_id == Train.id)
            .where(DelayRecord.actual_arrival.is_not(None))
            .where(DelayRecord.is_cancelled == False)
            .where(Train.zone.is_not(None))
            .group_by(Train.zone)
            .order_by(func.avg(DelayRecord.arrival_delay_minutes).desc())
            .limit(1)
        )
        stmt = self._apply_date_filter(stmt, start_date, end_date)
        row = self.db.execute(stmt).first()
        if not row:
            return None
        return {"zone": row.zone, "avg_delay_minutes": float(row.avg_delay or 0)}

    # ── Route Analytics ────────────────────────────────────────

    def get_route_stats(
        self,
        zone: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 20,
        order_by: str = "avg_delay_desc",
    ) -> list[dict]:
        """
        Per-route delay breakdown for the Analytics page.
        Joins to trains + stations for human-readable output.
        """
        origin = Station.__table__.alias("origin_s")
        dest   = Station.__table__.alias("dest_s")

        stmt = (
            select(
                Train.id.label("train_id"),
                Train.train_number,
                Train.name.label("train_name"),
                Train.category,
                Train.zone,
                origin.c.station_code.label("origin_code"),
                dest.c.station_code.label("destination_code"),
                func.round(func.avg(DelayRecord.arrival_delay_minutes), 1).label("avg_delay"),
                func.round(
                    func.percentile_cont(0.5).within_group(
                        DelayRecord.arrival_delay_minutes
                    ), 1
                ).label("median_delay"),
                func.round(
                    func.sum(case((DelayRecord.arrival_delay_minutes <= 5, 1), else_=0)).cast(Float)
                    / func.count() * 100, 1
                ).label("otp_percentage"),
                func.count(func.distinct(DelayRecord.journey_date)).label("total_runs"),
                func.sum(
                    case((DelayRecord.arrival_delay_minutes > 120, 1), else_=0)
                ).label("severe_count"),
            )
            .join(Train, DelayRecord.train_id == Train.id)
            .join(origin, Train.origin_station_id == origin.c.id)
            .join(dest, Train.destination_station_id == dest.c.id)
            .where(DelayRecord.station_id == Train.destination_station_id)
            .where(DelayRecord.actual_arrival.is_not(None))
            .where(DelayRecord.is_cancelled == False)
        )

        if zone:
            stmt = stmt.where(Train.zone == zone)
        if category:
            stmt = stmt.where(Train.category == category)

        stmt = self._apply_date_filter(stmt, start_date, end_date)
        stmt = stmt.group_by(
            Train.id, Train.train_number, Train.name, Train.category,
            Train.zone, origin.c.station_code, dest.c.station_code
        )

        if order_by == "avg_delay_desc":
            stmt = stmt.order_by(func.avg(DelayRecord.arrival_delay_minutes).desc())
        elif order_by == "otp_asc":
            stmt = stmt.order_by(func.avg(DelayRecord.arrival_delay_minutes).asc())

        stmt = stmt.limit(limit)
        rows = self.db.execute(stmt).all()
        return [row._asdict() for row in rows]

    # ── Zone Analytics ─────────────────────────────────────────

    def get_zone_stats(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        """Zone-wise OTP and delay breakdown."""
        stmt = (
            select(
                Train.zone,
                func.round(func.avg(DelayRecord.arrival_delay_minutes), 2).label("avg_delay"),
                func.round(
                    func.sum(case((DelayRecord.arrival_delay_minutes <= 5, 1), else_=0)).cast(Float)
                    / func.count() * 100, 2
                ).label("otp_percentage"),
                func.count().label("total_records"),
                func.round(
                    func.percentile_cont(0.9).within_group(DelayRecord.arrival_delay_minutes), 1
                ).label("p90_delay"),
                func.sum(
                    case((DelayRecord.arrival_delay_minutes > 120, 1), else_=0)
                ).label("severe_count"),
            )
            .join(Train, DelayRecord.train_id == Train.id)
            .where(DelayRecord.actual_arrival.is_not(None))
            .where(DelayRecord.is_cancelled == False)
            .where(Train.zone.is_not(None))
            .group_by(Train.zone)
            .order_by(func.avg(DelayRecord.arrival_delay_minutes).desc())
        )
        stmt = self._apply_date_filter(stmt, start_date, end_date)
        return [row._asdict() for row in self.db.execute(stmt).all()]

    # ── Seasonal Analytics ─────────────────────────────────────

    def get_seasonal_stats(self, year: Optional[int] = None) -> list[dict]:
        """Month-by-month delay pattern — shows monsoon/fog season effect."""
        stmt = (
            select(
                func.extract("month", DelayRecord.journey_date).label("month"),
                func.round(func.avg(DelayRecord.arrival_delay_minutes), 2).label("avg_delay"),
                func.round(
                    func.sum(case((DelayRecord.arrival_delay_minutes <= 5, 1), else_=0)).cast(Float)
                    / func.count() * 100, 2
                ).label("otp_percentage"),
                func.count().label("total_records"),
            )
            .where(DelayRecord.actual_arrival.is_not(None))
            .where(DelayRecord.is_cancelled == False)
            .group_by(func.extract("month", DelayRecord.journey_date))
            .order_by(func.extract("month", DelayRecord.journey_date))
        )
        if year:
            stmt = stmt.where(
                func.extract("year", DelayRecord.journey_date) == year
            )
        rows = self.db.execute(stmt).all()

        month_names = [
            "", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        return [
            {
                "month": int(row.month),
                "month_name": month_names[int(row.month)],
                "avg_delay_minutes": float(row.avg_delay or 0),
                "otp_percentage": float(row.otp_percentage or 0),
                "total_records": row.total_records,
                "is_monsoon": int(row.month) in (6, 7, 8, 9),
                "is_fog_season": int(row.month) in (12, 1),
            }
            for row in rows
        ]

    # ── Station Congestion ─────────────────────────────────────

    def get_station_stats(
        self,
        zone: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Station-level departure delay — measures congestion caused at each station."""
        stmt = (
            select(
                Station.station_code,
                Station.name.label("station_name"),
                Station.zone,
                func.round(func.avg(DelayRecord.departure_delay_minutes), 2).label("avg_departure_delay"),
                func.count().label("total_train_passes"),
            )
            .join(Station, DelayRecord.station_id == Station.id)
            .where(DelayRecord.actual_departure.is_not(None))
            .where(DelayRecord.is_cancelled == False)
        )
        if zone:
            stmt = stmt.where(Station.zone == zone)

        stmt = (
            stmt.group_by(Station.id, Station.station_code, Station.name, Station.zone)
            .having(func.count() > 50)   # Min 50 records for statistical significance
            .order_by(func.avg(DelayRecord.departure_delay_minutes).desc())
            .limit(limit)
        )
        return [row._asdict() for row in self.db.execute(stmt).all()]

    # ── Heatmap ────────────────────────────────────────────────

    def get_heatmap_data(
        self,
        metric: str = "avg_delay",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        """
        Lat/long + metric value for each station — feeds the Folium/Pydeck heatmap.
        """
        stmt = (
            select(
                Station.station_code,
                Station.name.label("station_name"),
                Station.latitude,
                Station.longitude,
                func.round(func.avg(DelayRecord.arrival_delay_minutes), 1).label("value"),
                func.count(func.distinct(DelayRecord.train_id)).label("total_trains"),
            )
            .join(Station, DelayRecord.station_id == Station.id)
            .where(DelayRecord.actual_arrival.is_not(None))
            .where(Station.latitude.is_not(None))
            .where(Station.longitude.is_not(None))
            .group_by(
                Station.station_code, Station.name, Station.latitude, Station.longitude
            )
            .having(func.count() > 20)
        )
        stmt = self._apply_date_filter(stmt, start_date, end_date)
        return [row._asdict() for row in self.db.execute(stmt).all()]

    # ── Helper ─────────────────────────────────────────────────

    def _apply_date_filter(self, stmt, start_date, end_date):
        if start_date:
            stmt = stmt.where(DelayRecord.journey_date >= start_date)
        if end_date:
            stmt = stmt.where(DelayRecord.journey_date <= end_date)
        return stmt


# Fix missing import — needed for OTP % calculation in case() expressions
from sqlalchemy import Float  # noqa: E402 (intentional late import)