from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.v1 import auth, analytics, predictions, anomalies, forecast, reports, admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: pre-load ML models into memory
    from app.services.prediction_service import PredictionService
    app.state.predictor = PredictionService.load()  # Load XGBoost once at startup
    yield
    # Shutdown cleanup

app = FastAPI(
    title="India Railways Delay Intelligence API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(auth.router,        prefix="/api/v1/auth",       tags=["Auth"])
app.include_router(analytics.router,   prefix="/api/v1/analytics",  tags=["Analytics"])
app.include_router(predictions.router, prefix="/api/v1/predictions", tags=["Predictions"])
app.include_router(anomalies.router,   prefix="/api/v1/anomalies",  tags=["Anomalies"])
app.include_router(forecast.router,    prefix="/api/v1/forecast",   tags=["Forecast"])
app.include_router(reports.router,     prefix="/api/v1/reports",    tags=["Reports"])
app.include_router(admin.router,       prefix="/api/v1/admin",      tags=["Admin"])