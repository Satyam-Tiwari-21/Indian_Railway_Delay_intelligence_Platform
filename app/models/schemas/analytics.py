# app/models/schemas/analytics.py

from datetime import date
from typing import Optional
from pydantic import BaseModel


class OverviewResponse(BaseModel):
    """Network-wide KPIs — shown on the Home dashboard page."""
    total_active_trains: int
    total_stations: int
    avg_delay_minutes: float
    otp_percentage: float           # On-Time Performance %
    total_records_analysed: int
    worst_zone: Optional[str]
    worst_zone_avg_delay: Optional[float]
    open_anomalies: int
    date_range_start: date
    date_range_end: date


class RouteStats(BaseModel):
    """Per-route delay breakdown — for Analytics page route table."""
    train_id: int
    train_number: str
    train_name: str
    category: str
    zone: Optional[str]
    origin_code: str
    destination_code: str
    avg_delay_minutes: float
    median_delay_minutes: float
    otp_percentage: float
    total_runs: int
    severe_delay_count: int

    model_config = {"from_attributes": True}


class ZoneStats(BaseModel):
    """Zone-level aggregation."""
    zone: str
    avg_delay_minutes: float
    otp_percentage: float
    total_records: int
    p90_delay_minutes: float        # 90th percentile — captures worst cases
    severe_count: int


class StationStats(BaseModel):
    """Station congestion scoring."""
    station_code: str
    station_name: str
    zone: Optional[str]
    avg_departure_delay: float      # Delay *caused* at this station
    total_train_passes: int
    congestion_score: float         # Normalised 0–100


class HeatmapPoint(BaseModel):
    """One point on the delay heatmap — station with avg delay."""
    station_code: str
    station_name: str
    latitude: float
    longitude: float
    value: float                    # e.g., avg_delay_minutes
    total_trains: int


class SeasonalStats(BaseModel):
    """Monthly delay pattern — for the seasonal chart."""
    month: int                      # 1–12
    month_name: str                 # 'January', 'February', ...
    avg_delay_minutes: float
    otp_percentage: float
    total_records: int
    is_monsoon: bool
    is_fog_season: bool


class TopRouteEntry(BaseModel):
    rank: int
    train_number: str
    train_name: str
    origin_code: str
    destination_code: str
    avg_delay_minutes: float
    otp_percentage: float