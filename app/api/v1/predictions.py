# app/api/v1/predictions.py

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.db.user import User
from app.models.schemas.prediction import (
    BatchPredictionRequest,
    BatchPredictionResponse,
    PredictionRequest,
    PredictionResponse,
)
from app.repositories.prediction_repository import PredictionRepository
from app.services.prediction_service import (
    PredictionService,
    predict_batch,
    predict_delay,
)

router = APIRouter()


def _get_predictor(request: Request) -> PredictionService:
    """
    Get the pre-loaded PredictionService from app state.
    Loaded once at startup in main.py lifespan.
    """
    predictor = getattr(request.app.state, "predictor", None)
    if predictor is None:
        # Lazy-load if startup loading was skipped
        request.app.state.predictor = PredictionService.load()
        predictor = request.app.state.predictor
    return predictor


@router.post(
    "/delay",
    response_model=PredictionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Predict arrival delay for a train at a station",
)
def predict(
    body: PredictionRequest,
    request: Request,
    user: User = Depends(require_permission("can_predict")),
    db: Session = Depends(get_db),
):
    """
    Predict how late a train will be at a specific station on a given date.
    Returns the predicted delay in minutes, risk level, confidence interval,
    and optional SHAP explanation of what factors drove the prediction.
    """
    predictor = _get_predictor(request)
    try:
        return predict_delay(body, db, predictor, user_id=str(user.id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/batch",
    response_model=BatchPredictionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run up to 50 predictions in a single API call",
)
def predict_batch_endpoint(
    body: BatchPredictionRequest,
    request: Request,
    user: User = Depends(require_permission("can_predict")),
    db: Session = Depends(get_db),
):
    """Batch prediction — useful for pre-computing tomorrow's delays for a zone."""
    predictor = _get_predictor(request)
    return predict_batch(body, db, predictor, user_id=str(user.id))


@router.get(
    "/history",
    response_model=list[PredictionResponse],
    summary="Get the current user's prediction history",
)
def get_history(
    skip: int = 0,
    limit: int = 50,
    user: User = Depends(require_permission("can_predict")),
    db: Session = Depends(get_db),
):
    """Returns the last N predictions made by the authenticated user."""
    predictions = PredictionRepository(db).get_user_history(
        user_id=str(user.id), skip=skip, limit=limit
    )
    results = []
    for p in predictions:
        from app.services.prediction_service import _classify_delay, _class_probabilities
        from app.models.schemas.prediction import PredictionExplanation, ShapFactor

        shap_factors = []
        if p.shap_values:
            for sv in p.shap_values:
                try:
                    shap_factors.append(ShapFactor(**sv))
                except Exception:
                    pass

        results.append(PredictionResponse(
            prediction_id=p.id,
            train_number=p.train.train_number if p.train else "N/A",
            train_name=p.train.name if p.train else "N/A",
            query_station=p.station.name if p.station else "N/A",
            journey_date=p.predicted_for_date,
            predicted_delay_minutes=p.predicted_delay_minutes,
            confidence_lower=p.confidence_lower,
            confidence_upper=p.confidence_upper,
            risk_level=_classify_delay(p.predicted_delay_minutes),
            class_probabilities=_class_probabilities(p.predicted_delay_minutes),
            explanation=PredictionExplanation(
                base_value=18.0,
                top_factors=shap_factors,
            ) if shap_factors else None,
            model_name=p.model_name,
            model_version=p.model_version,
            inference_time_ms=p.inference_time_ms,
            created_at=p.created_at,
        ))
    return results


@router.get(
    "/{prediction_id}",
    response_model=PredictionResponse,
    summary="Get a specific prediction by ID",
)
def get_prediction(
    prediction_id: int,
    user: User = Depends(require_permission("can_predict")),
    db: Session = Depends(get_db),
):
    repo = PredictionRepository(db)
    p = repo.get_by_id_with_relations(prediction_id)
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found")

    from app.services.prediction_service import _classify_delay, _class_probabilities
    from app.models.schemas.prediction import PredictionExplanation, ShapFactor

    shap_factors = []
    if p.shap_values:
        for sv in p.shap_values:
            try:
                shap_factors.append(ShapFactor(**sv))
            except Exception:
                pass

    return PredictionResponse(
        prediction_id=p.id,
        train_number=p.train.train_number if p.train else "N/A",
        train_name=p.train.name if p.train else "N/A",
        query_station=p.station.name if p.station else "N/A",
        journey_date=p.predicted_for_date,
        predicted_delay_minutes=p.predicted_delay_minutes,
        confidence_lower=p.confidence_lower,
        confidence_upper=p.confidence_upper,
        risk_level=_classify_delay(p.predicted_delay_minutes),
        class_probabilities=_class_probabilities(p.predicted_delay_minutes),
        explanation=PredictionExplanation(
            base_value=18.0, top_factors=shap_factors
        ) if shap_factors else None,
        model_name=p.model_name,
        model_version=p.model_version,
        inference_time_ms=p.inference_time_ms,
        created_at=p.created_at,
    )