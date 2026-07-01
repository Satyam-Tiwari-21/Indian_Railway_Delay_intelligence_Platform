# ml/utils/metrics.py
# Custom evaluation metrics for Indian Railways delay prediction.
# Used by evaluation_pipeline.py and training_pipeline.py.

import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    classification_report,
    confusion_matrix,
)


# ── Regression Metrics ─────────────────────────────────────────

def compute_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """
    Full metric suite for delay regression models.
    within_15min_pct is the most operationally meaningful — predicting within
    15 minutes is useful; beyond that the prediction loses practical value.
    """
    mae  = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2   = r2_score(y_true, y_pred)
    residuals = y_pred - y_true

    return {
        "mae":               round(float(mae), 3),
        "rmse":              round(float(rmse), 3),
        "r2":                round(float(r2), 4),
        "within_5min_pct":   round(float(np.mean(np.abs(residuals) <= 5) * 100),  2),
        "within_15min_pct":  round(float(np.mean(np.abs(residuals) <= 15) * 100), 2),
        "within_30min_pct":  round(float(np.mean(np.abs(residuals) <= 30) * 100), 2),
        "mean_bias":         round(float(np.mean(residuals)), 3),  # Positive = over-predicts delay
        "p90_error":         round(float(np.percentile(np.abs(residuals), 90)), 2),
    }


def print_regression_report(model_name: str, metrics: dict) -> None:
    print(f"\n{'─'*50}")
    print(f"  {model_name}")
    print(f"{'─'*50}")
    print(f"  MAE:              {metrics['mae']:.2f} min")
    print(f"  RMSE:             {metrics['rmse']:.2f} min")
    print(f"  R²:               {metrics['r2']:.4f}")
    print(f"  Within 5 min:     {metrics['within_5min_pct']:.1f}%")
    print(f"  Within 15 min:    {metrics['within_15min_pct']:.1f}%")
    print(f"  Within 30 min:    {metrics['within_30min_pct']:.1f}%")
    print(f"  Mean bias:        {metrics['mean_bias']:+.2f} min")
    print(f"  P90 error:        {metrics['p90_error']:.1f} min")


def compare_models(results: dict[str, dict]) -> pd.DataFrame:
    """
    Build a comparison table from {model_name: metrics} dict.
    Printed at end of training_pipeline.py.
    """
    rows = []
    for name, m in results.items():
        rows.append({
            "Model":          name,
            "MAE (min)":      m["mae"],
            "RMSE (min)":     m["rmse"],
            "R²":             m["r2"],
            "Within 15min %": m["within_15min_pct"],
            "Within 30min %": m["within_30min_pct"],
        })
    df = pd.DataFrame(rows).sort_values("MAE (min)")
    return df


# ── Classification Metrics ─────────────────────────────────────

def compute_classification_metrics(y_true, y_pred) -> dict:
    """Metrics for the 4-class delay classification model."""
    labels = ["ON_TIME", "SLIGHT", "MODERATE", "SEVERE"]
    report = classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
    cm     = confusion_matrix(y_true, y_pred, labels=labels)
    return {
        "classification_report": report,
        "confusion_matrix":      cm.tolist(),
        "accuracy":              round(report["accuracy"], 4),
        "macro_f1":              round(report["macro avg"]["f1-score"], 4),
    }


# ── Anomaly Detection Metrics ──────────────────────────────────

def compute_anomaly_metrics(
    y_true_binary: np.ndarray,
    anomaly_scores: np.ndarray,
    threshold: float = -0.1,
) -> dict:
    """
    y_true_binary: 1 = actual anomaly, 0 = normal
    anomaly_scores: Isolation Forest score_samples() output
    """
    from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score

    y_pred = (anomaly_scores < threshold).astype(int)

    try:
        auc = roc_auc_score(y_true_binary, -anomaly_scores)
    except Exception:
        auc = None

    return {
        "precision": round(float(precision_score(y_true_binary, y_pred, zero_division=0)), 4),
        "recall":    round(float(recall_score(y_true_binary, y_pred, zero_division=0)),    4),
        "f1":        round(float(f1_score(y_true_binary, y_pred, zero_division=0)),        4),
        "auc_roc":   round(float(auc), 4) if auc else None,
        "flagged_pct": round(float(y_pred.mean() * 100), 2),
    }