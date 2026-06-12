# app/models/schemas/prediction.py

from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class DelayClass(str, Enum):
    ON_TIME  = "ON_TIME"   # <= 5 min
    SLIGHT   = "SLIGHT"    # 5–30 min
    MODERATE = "MODERATE"  # 30–120 min
    SEVERE   = "SEVERE"    # > 120 min


class ShapFactor(BaseModel):
    """One SHAP feature contribution — explains WHY the model predicted this delay."""
    feature: str
    contribution_minutes: float
    direction: str          # '+' = increases delay, '-' = decreases delay
    display_name: str       # Human-readable: 'is_monsoon' → 'Monsoon Season'


class PredictionExplanation(BaseModel):
    base_value: float       # Average prediction without any features
    top_factors: list[ShapFactor]


class ClassProbabilities(BaseModel):
    ON_TIME:  float
    SLIGHT:   float
    MODERATE: float
    SEVERE:   float


class PredictionRequest(BaseModel):
    train_number: str       = Field(..., example="12301")
    query_station_code: str = Field(..., example="NDLS")
    journey_date: date      = Field(..., example="2025-08-15")
    include_explanation: bool = Field(True, description="Include SHAP explanation")

    @field_validator("train_number")
    @classmethod
    def train_number_valid(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or not (4 <= len(v) <= 5):
            raise ValueError("train_number must be a 4-5 digit number e.g. '12301'")
        return v

    @field_validator("query_station_code")
    @classmethod
    def station_code_upper(cls, v: str) -> str:
        return v.strip().upper()


class PredictionResponse(BaseModel):
    prediction_id: int
    train_number: str
    train_name: str
    query_station: str
    journey_date: date

    predicted_delay_minutes: float
    confidence_lower: Optional[float]
    confidence_upper: Optional[float]

    risk_level: DelayClass
    class_probabilities: ClassProbabilities

    explanation: Optional[PredictionExplanation]

    model_name: str
    model_version: str
    inference_time_ms: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class BatchPredictionRequest(BaseModel):
    predictions: list[PredictionRequest] = Field(
        ..., max_length=50, description="Max 50 predictions per batch"
    )


class BatchPredictionResponse(BaseModel):
    total: int
    results: list[PredictionResponse]
    failed: list[dict]      # {train_number, error} for any that failed