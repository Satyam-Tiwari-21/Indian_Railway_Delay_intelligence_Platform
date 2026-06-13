# app/services/prediction_service.py
# Loads the XGBoost model at startup, runs inference for each request.
# Falls back to a heuristic mock if no model file exists yet (Phase 1/2).
# Real ML model replaces mock automatically in Phase 5 when you run ml/train.py.

import time
from datetime import date
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.schemas.prediction import (
    BatchPredictionRequest,
    BatchPredictionResponse,
    ClassProbabilities,
    DelayClass,
    PredictionExplanation,
    PredictionRequest,
    PredictionResponse,
    ShapFactor,
)
from app.repositories.prediction_repository import PredictionRepository
from app.repositories.train_repository import TrainRepository
from app.services.auth_service import log_audit

logger = get_logger(__name__)


# ── Delay Classification ───────────────────────────────────────

def _classify_delay(minutes: float) -> DelayClass:
    if minutes <= 5:   return DelayClass.ON_TIME
    if minutes <= 30:  return DelayClass.SLIGHT
    if minutes <= 120: return DelayClass.MODERATE
    return DelayClass.SEVERE


def _class_probabilities(minutes: float) -> ClassProbabilities:
    """
    Generate realistic class probabilities from a single predicted value.
    Used by both real model and mock.
    """
    if minutes <= 5:
        return ClassProbabilities(ON_TIME=0.78, SLIGHT=0.17, MODERATE=0.04, SEVERE=0.01)
    if minutes <= 30:
        return ClassProbabilities(ON_TIME=0.12, SLIGHT=0.62, MODERATE=0.22, SEVERE=0.04)
    if minutes <= 120:
        return ClassProbabilities(ON_TIME=0.05, SLIGHT=0.18, MODERATE=0.57, SEVERE=0.20)
    return ClassProbabilities(ON_TIME=0.02, SLIGHT=0.08, MODERATE=0.25, SEVERE=0.65)


# ── Heuristic Mock Predictor ───────────────────────────────────
# Used automatically when no trained model exists.
# Produces realistic predictions using Indian Railways domain knowledge.

def _mock_predict(features: dict) -> dict:
    """
    Domain-knowledge-based delay predictor.
    Replicates key patterns observed in Indian Railways historical data.
    """
    base = features.get("hist_delay_30d", 18.0) or 18.0

    # India seasonal multipliers (biggest delay drivers)
    if features.get("is_monsoon"):      base *= 1.85   # Jun–Sep: flooding, signal failures
    if features.get("is_fog_season"):   base *= 1.65   # Dec–Jan: dense fog on NR
    if features.get("is_holiday_week"): base *= 1.30   # Diwali, Holi, Eid rush
    if features.get("is_weekend"):      base *= 1.10

    # Train category (premium trains are better managed)
    factors = {
        "Rajdhani":  0.55, "Shatabdi": 0.60, "Duronto": 0.65,
        "Superfast": 0.80, "Mail": 1.00, "Express": 1.00, "Passenger": 1.45,
        "MEMU": 0.90, "EMU": 0.85,
    }
    base *= factors.get(features.get("category", "Express"), 1.0)

    # Delay compounds along the route — later stops have more delay
    stop_pct = features.get("stop_position_pct", 0.5)
    base *= (0.6 + stop_pct * 0.8)

    # Mock SHAP explanation factors
    shap = [
        ShapFactor(
            feature="hist_delay_30d",
            contribution_minutes=round(base * 0.35, 1),
            direction="+",
            display_name="30-Day Historical Avg Delay",
        ),
        ShapFactor(
            feature="is_monsoon" if features.get("is_monsoon") else "stop_position_pct",
            contribution_minutes=round(base * 0.25, 1),
            direction="+",
            display_name="Monsoon Season" if features.get("is_monsoon") else "Stop Position",
        ),
        ShapFactor(
            feature="category",
            contribution_minutes=round(base * 0.15, 1),
            direction="-" if factors.get(features.get("category", "Express"), 1.0) < 1 else "+",
            display_name=f"Train Category ({features.get('category', 'Express')})",
        ),
    ]

    return {
        "predicted_delay": max(0.0, round(base, 1)),
        "shap_factors": shap,
        "base_value": 18.0,
        "is_mock": True,
    }


# ── Feature Engineering ────────────────────────────────────────

def _build_features(
    train,
    station,
    journey_date: date,
    db: Session,
) -> dict:
    """
    Build the feature vector for a single prediction request.
    In Phase 5 this is replaced by ml/pipelines/feature_pipeline.py.
    """
    month = journey_date.month
    dow   = journey_date.weekday()  # 0=Mon, 6=Sun

    # Get 30-day historical avg delay for this train
    from sqlalchemy import select, func
    from app.models.db.delay_record import DelayRecord
    from datetime import timedelta

    cutoff = journey_date - timedelta(days=30)
    hist_avg = db.scalar(
        select(func.avg(DelayRecord.arrival_delay_minutes))
        .where(DelayRecord.train_id == train.id)
        .where(DelayRecord.journey_date >= cutoff)
        .where(DelayRecord.journey_date < journey_date)
    )

    return {
        "train_id":            train.id,
        "train_number":        train.train_number,
        "category":            train.category,
        "zone":                train.zone,
        "distance_km":         train.distance_km or 1000,
        "total_stops":         train.total_stops or 20,
        "month":               month,
        "day_of_week":         dow,
        "is_monsoon":          month in (6, 7, 8, 9),
        "is_fog_season":       month in (12, 1),
        "is_summer_peak":      month in (4, 5),
        "is_harvest_fest":     month in (10, 11),
        "is_weekend":          dow >= 5,
        "is_holiday_week":     False,  # Phase 5: plug in indian_calendar.py
        "hist_delay_30d":      float(hist_avg or 18.0),
        "stop_position_pct":   0.5,    # Phase 5: derive from routes table
    }


# ── Prediction Service ─────────────────────────────────────────

class PredictionService:
    """
    Singleton — loaded once at FastAPI startup via lifespan.
    Wraps model loading and inference in a clean interface.
    """

    def __init__(self, model=None, is_mock: bool = True):
        self._model = model
        self.is_mock = is_mock

    @classmethod
    def load(cls) -> "PredictionService":
        """
        Try to load the trained XGBoost model from disk.
        Falls back to heuristic mock if model file not found.
        Call once at startup: app.state.predictor = PredictionService.load()
        """
        model_path = Path(settings.MODEL_DIR) / f"{settings.ACTIVE_MODEL_NAME}.pkl"
        try:
            import joblib
            model = joblib.load(model_path)
            logger.info("ML model loaded from disk", path=str(model_path))
            return cls(model=model, is_mock=False)
        except FileNotFoundError:
            logger.warning(
                "Model file not found — using heuristic mock predictor. "
                "Run ml/train.py to train real models.",
                expected_path=str(model_path),
            )
            return cls(model=None, is_mock=True)

    def _run_inference(self, features: dict) -> dict:
        """Run model or mock. Always returns same structure."""
        if self.is_mock:
            return _mock_predict(features)

        # Real XGBoost inference
        try:
            import numpy as np
            import shap

            feature_cols = [
                "month", "day_of_week", "is_monsoon", "is_fog_season",
                "is_summer_peak", "is_harvest_fest", "is_weekend",
                "is_holiday_week", "hist_delay_30d", "stop_position_pct",
                "distance_km", "total_stops",
            ]
            X = np.array([[features.get(c, 0) for c in feature_cols]])
            predicted = float(self._model.predict(X)[0])

            # SHAP explanation
            explainer = shap.TreeExplainer(self._model)
            sv = explainer.shap_values(X)[0]
            shap_factors = [
                ShapFactor(
                    feature=feature_cols[i],
                    contribution_minutes=round(float(sv[i]), 1),
                    direction="+" if sv[i] >= 0 else "-",
                    display_name=feature_cols[i].replace("_", " ").title(),
                )
                for i in np.argsort(np.abs(sv))[::-1][:5]  # Top 5
            ]

            return {
                "predicted_delay": max(0.0, round(predicted, 1)),
                "shap_factors": shap_factors,
                "base_value": float(explainer.expected_value),
                "is_mock": False,
            }
        except Exception as exc:
            logger.error("Real model inference failed, falling back to mock", error=str(exc))
            return _mock_predict(features)


# ── Public API ─────────────────────────────────────────────────

def predict_delay(
    request: PredictionRequest,
    db: Session,
    predictor: "PredictionService",
    user_id: Optional[str] = None,
) -> PredictionResponse:
    """
    Run a single delay prediction.
    Called by POST /api/v1/predictions/delay
    """
    start_ms = time.monotonic()

    # Load train and station
    train_repo = TrainRepository(db)
    train = train_repo.get_by_number_or_404(request.train_number)
    station = train_repo.get_station_by_code(request.query_station_code)
    if station is None:
        raise ValueError(f"Station code '{request.query_station_code}' not found")

    # Build features
    features = _build_features(train, station, request.journey_date, db)

    # Run model
    result = predictor._run_inference(features)
    predicted = result["predicted_delay"]
    inference_ms = int((time.monotonic() - start_ms) * 1000)

    # Confidence interval (±30% for mock, real CI from quantile regression in Phase 5)
    ci_lower = round(predicted * 0.7, 1)
    ci_upper = round(predicted * 1.3, 1)

    risk = _classify_delay(predicted)
    probs = _class_probabilities(predicted)

    explanation = None
    if request.include_explanation:
        explanation = PredictionExplanation(
            base_value=result.get("base_value", 18.0),
            top_factors=result.get("shap_factors", []),
        )

    # Store in DB
    pred_repo = PredictionRepository(db)
    stored = pred_repo.store({
        "train_id":                 train.id,
        "station_id":               station.id,
        "predicted_for_date":       request.journey_date,
        "model_name":               settings.ACTIVE_MODEL_NAME,
        "model_version":            "mock-1.0" if predictor.is_mock else "1.0",
        "predicted_delay_minutes":  predicted,
        "confidence_lower":         ci_lower,
        "confidence_upper":         ci_upper,
        "risk_level":               risk.value,
        "class_probabilities":      probs.model_dump(),
        "shap_values":              [f.model_dump() for f in (explanation.top_factors if explanation else [])],
        "input_features":           features,
        "requested_by":             user_id,
        "inference_time_ms":        inference_ms,
    })

    # Audit
    log_audit(
        db=db, action="PREDICT", user_id=user_id,
        resource_type="prediction", resource_id=str(stored.id),
        response_status=200, duration_ms=inference_ms,
    )

    logger.info(
        "Prediction completed",
        train=request.train_number,
        predicted_delay=predicted,
        risk=risk.value,
        is_mock=result.get("is_mock"),
        inference_ms=inference_ms,
    )

    return PredictionResponse(
        prediction_id=stored.id,
        train_number=train.train_number,
        train_name=train.name,
        query_station=station.name,
        journey_date=request.journey_date,
        predicted_delay_minutes=predicted,
        confidence_lower=ci_lower,
        confidence_upper=ci_upper,
        risk_level=risk,
        class_probabilities=probs,
        explanation=explanation,
        model_name=settings.ACTIVE_MODEL_NAME,
        model_version="mock-1.0" if predictor.is_mock else "1.0",
        inference_time_ms=inference_ms,
        created_at=stored.created_at,
    )


def predict_batch(
    request: BatchPredictionRequest,
    db: Session,
    predictor: "PredictionService",
    user_id: Optional[str] = None,
) -> BatchPredictionResponse:
    """Run up to 50 predictions in one call."""
    results = []
    failed = []

    for pred_req in request.predictions:
        try:
            result = predict_delay(pred_req, db, predictor, user_id)
            results.append(result)
        except Exception as exc:
            failed.append({
                "train_number": pred_req.train_number,
                "station_code": pred_req.query_station_code,
                "error": str(exc),
            })

    return BatchPredictionResponse(
        total=len(results),
        results=results,
        failed=failed,
    )