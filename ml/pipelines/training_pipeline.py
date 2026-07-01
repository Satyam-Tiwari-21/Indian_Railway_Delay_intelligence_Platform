# ml/pipelines/training_pipeline.py
# Trains all models, logs experiments to MLflow, saves best model to disk.
# Called by ml/train.py CLI.

import sys
import time
from pathlib import Path

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from data.etl.feature_engineering import FEATURE_COLUMNS
from ml.models.delay_predictor  import XGBoostDelayPredictor
from ml.models.classifier       import DelayClassifier
from ml.models.anomaly_detector import AnomalyDetector
from ml.utils.metrics import compute_regression_metrics, compare_models, print_regression_report


MODEL_DIR = Path("ml/saved_models")


# ── Baseline models for comparison ────────────────────────────

def _train_linear_regression(X_train, y_train, X_test, y_test) -> dict:
    model = LinearRegression()
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    return {"model": model, "metrics": compute_regression_metrics(y_test, preds)}


def _train_random_forest(X_train, y_train, X_test, y_test) -> dict:
    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=5,
        n_jobs=-1,
        random_state=42,
    )
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    return {"model": model, "metrics": compute_regression_metrics(y_test, preds)}


def _train_lightgbm(X_train, y_train, X_test, y_test) -> dict:
    try:
        from lightgbm import LGBMRegressor
        model = LGBMRegressor(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        )
        model.fit(X_train, y_train, eval_set=[(X_test, y_test)])
        preds = model.predict(X_test)
        return {"model": model, "metrics": compute_regression_metrics(y_test, preds)}
    except ImportError:
        print("  ⚠️  LightGBM not installed — skipping")
        return None


# ── Main training pipeline ─────────────────────────────────────

def run_training(
    use_mlflow: bool = True,
    model_dir: str = "ml/saved_models",
):
    """
    Full training pipeline:
    1. Load data from DB
    2. Prepare features
    3. Train 4 regression models + compare
    4. Train classifier
    5. Train anomaly detector
    6. Train zone forecasters
    7. Log to MLflow
    8. Save best model (XGBoost) to disk
    """
    import mlflow
    import mlflow.sklearn

    from app.core.config import settings
    from ml.pipelines.feature_pipeline import load_from_db, prepare_features

    MODEL_DIR = Path(model_dir)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    if use_mlflow:
        mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
        mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)
        print(f"MLflow tracking: {settings.MLFLOW_TRACKING_URI}")

    # ── 1. Load data ───────────────────────────────────────────
    print("\n" + "="*60)
    print("STEP 1/5 — Loading & preparing data")
    print("="*60)

    df = load_from_db()
    X_train, X_test, y_train, y_test, y_train_cls, y_test_cls, train_df, test_df = \
        prepare_features(df)

    # ── 2. Train regression models ─────────────────────────────
    print("\n" + "="*60)
    print("STEP 2/5 — Training regression models")
    print("="*60)

    all_results = {}
    parent_run_id = None

    with mlflow.start_run(run_name="model_comparison") as parent_run:
        parent_run_id = parent_run.info.run_id
        mlflow.log_param("n_train", len(X_train))
        mlflow.log_param("n_test",  len(X_test))
        mlflow.log_param("n_features", len(FEATURE_COLUMNS))

        # Linear Regression (baseline)
        print("\n[1/4] Linear Regression...")
        t0 = time.time()
        lr_result = _train_linear_regression(X_train, y_train, X_test, y_test)
        print_regression_report("Linear Regression", lr_result["metrics"])
        all_results["Linear Regression"] = lr_result["metrics"]

        with mlflow.start_run(run_name="linear_regression", nested=True):
            mlflow.log_metrics(lr_result["metrics"])
            mlflow.log_param("model_type", "linear_regression")

        # Random Forest
        print(f"\n[2/4] Random Forest...")
        rf_result = _train_random_forest(X_train, y_train, X_test, y_test)
        print_regression_report("Random Forest", rf_result["metrics"])
        all_results["Random Forest"] = rf_result["metrics"]

        with mlflow.start_run(run_name="random_forest", nested=True):
            mlflow.log_metrics(rf_result["metrics"])
            mlflow.log_param("model_type", "random_forest")

        # XGBoost (primary model)
        print(f"\n[3/4] XGBoost (primary model)...")
        xgb_predictor = XGBoostDelayPredictor()
        xgb_predictor.fit(X_train, y_train, X_test, y_test)
        xgb_preds = xgb_predictor.predict(X_test)
        xgb_metrics = compute_regression_metrics(y_test, xgb_preds)
        print_regression_report("XGBoost", xgb_metrics)
        all_results["XGBoost"] = xgb_metrics

        with mlflow.start_run(run_name="xgboost", nested=True):
            mlflow.log_metrics(xgb_metrics)
            mlflow.log_param("model_type", "xgboost")
            mlflow.log_param("n_estimators", 500)
            mlflow.log_param("max_depth", 6)
            mlflow.log_param("learning_rate", 0.05)
            mlflow.sklearn.log_model(xgb_predictor.model, "xgboost_model")

        # LightGBM
        print(f"\n[4/4] LightGBM...")
        lgb_result = _train_lightgbm(X_train, y_train, X_test, y_test)
        if lgb_result:
            print_regression_report("LightGBM", lgb_result["metrics"])
            all_results["LightGBM"] = lgb_result["metrics"]
            with mlflow.start_run(run_name="lightgbm", nested=True):
                mlflow.log_metrics(lgb_result["metrics"])
                mlflow.log_param("model_type", "lightgbm")

        # Print comparison table
        print("\n" + "="*60)
        print("MODEL COMPARISON")
        print("="*60)
        comparison = compare_models(all_results)
        print(comparison.to_string(index=False))

    # ── 3. Save XGBoost (winner) ───────────────────────────────
    print("\n" + "="*60)
    print("STEP 3/5 — Saving XGBoost model")
    print("="*60)
    xgb_path = MODEL_DIR / "xgboost_delay_predictor.pkl"
    xgb_predictor.save(str(xgb_path))

    # ── 4. Train classifier ────────────────────────────────────
    print("\n" + "="*60)
    print("STEP 4/5 — Training delay classifier")
    print("="*60)
    classifier = DelayClassifier()
    classifier.fit(X_train, y_train_cls, X_test, y_test_cls)
    clf_path = MODEL_DIR / "delay_classifier.pkl"
    classifier.save(str(clf_path))

    # ── 5. Train anomaly detector ──────────────────────────────
    print("\n" + "="*60)
    print("STEP 5/5 — Training anomaly detector")
    print("="*60)
    detector = AnomalyDetector()
    detector.fit(train_df)

    # Run detection on test set to see how it performs
    detected = detector.detect(test_df)
    n_anomalies = detected["is_anomaly"].sum()
    print(f"  Flagged {n_anomalies:,} anomalies in test set")

    detector_path = MODEL_DIR / "anomaly_detector.pkl"
    detector.save(str(detector_path))

    # ── Summary ────────────────────────────────────────────────
    print("\n" + "="*60)
    print("TRAINING COMPLETE")
    print("="*60)
    print(f"  XGBoost MAE:    {xgb_metrics['mae']:.2f} min")
    print(f"  Within 15 min:  {xgb_metrics['within_15min_pct']:.1f}%")
    print(f"  Models saved to: {MODEL_DIR}/")
    print(f"  MLflow run:     {parent_run_id}")
    print(f"\n  The API will automatically use the new model on next restart.")
    print(f"  Or trigger reload: POST /api/v1/admin/ml/retrain")

    return {
        "xgb_metrics":      xgb_metrics,
        "all_model_results":all_results,
        "model_paths": {
            "predictor":        str(xgb_path),
            "classifier":       str(clf_path),
            "anomaly_detector": str(detector_path),
        }
    }