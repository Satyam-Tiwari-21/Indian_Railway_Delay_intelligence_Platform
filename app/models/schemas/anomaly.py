# app/models/schemas/anomaly.py

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class AnomalyOut(BaseModel):
    id: int
    train_number: Optional[str]
    train_name: Optional[str]
    station_code: Optional[str]
    anomaly_date: date
    anomaly_score: float
    z_score: Optional[float]
    anomaly_type: Optional[str]
    severity: Optional[str]
    explanation: Optional[str]
    affected_train_count: int
    is_resolved: bool
    resolved_at: Optional[datetime]
    resolution_note: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class AnomalyFeed(BaseModel):
    total: int
    critical_count: int
    high_count: int
    medium_count: int
    anomalies: list[AnomalyOut]


class ResolveRequest(BaseModel):
    resolution_note: str


class AnomalyStats(BaseModel):
    date_range_start: date
    date_range_end: date
    total_anomalies: int
    by_type: dict[str, int]
    by_severity: dict[str, int]
    resolution_rate: float          # % of anomalies resolved