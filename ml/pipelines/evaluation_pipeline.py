# ml/pipelines/evaluation_pipeline.py
# Load a trained model and run full evaluation:
# metrics, SHAP summary plot, feature importance, confusion matrix.
# Called by ml/evaluate.py CLI.

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from data.etl.feature_engineering import FEATURE_COLUMNS
from ml.models.delay_predictor import XGBoostDelayPredictor
from ml.models.classifier import DelayClassifier, DELAY_CLASSES
from ml.utils.metrics import (
    compute_regression_metrics,
    compute_classification_metrics,
    print_regression_report,
)
from ml.utils.shap_explainer import generate_shap_summary

OUTPUT_DIR = Path("ml/saved_models/evaluation")


def run_evaluation(
    predictor_path: str = "ml/saved_models/xgboost_delay_predictor.pkl",
    classifier_path: str = "ml/saved_models/delay_classifier.pkl",
):
    """
    Full evaluation of the trained models.
    Generates metrics + plots saved to ml/saved_models/evaluation/
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    from ml.pipelines.feature_pipeline import load_from_db, prepare_features

    # ── Load data ──────────────────────────────────────────────
    print("Loading data for evaluation...")
    df = load_from_db()
    X_train, X_test, y_train, y_test, y_train_cls, y_test_cls, _, test_df = \
        prepare_features(df)

    # ── Load models ────────────────────────────────────────────
    print(f"\nLoading predictor: {predictor_path}")
    predictor = XGBoostDelayPredictor.load(predictor_path)

    print(f"Loading classifier: {classifier_path}")
    classifier = DelayClassifier.load(classifier_path)

    # ── Regression evaluation ──────────────────────────────────
    print("\n" + "="*55)
    print("REGRESSION MODEL EVALUATION")
    print("="*55)
    y_pred = predictor.predict(X_test)
    metrics = compute_regression_metrics(y_test, y_pred)
    print_regression_report("XGBoost Delay Predictor", metrics)

    # Residual plot
    _plot_residuals(y_test, y_pred)

    # Prediction vs actual scatter
    _plot_pred_vs_actual(y_test, y_pred)

    # ── SHAP summary ───────────────────────────────────────────
    print("\nGenerating SHAP summary plot...")
    sample_size = min(500, len(X_test))
    X_sample = X_test[:sample_size]
    shap_path = str(OUTPUT_DIR / "shap_summary.png")
    generate_shap_summary(predictor.model, X_sample, FEATURE_COLUMNS, shap_path)

    # ── Feature importance bar chart ───────────────────────────
    _plot_feature_importance(predictor)

    # ── Classification evaluation ──────────────────────────────
    print("\n" + "="*55)
    print("CLASSIFICATION MODEL EVALUATION")
    print("="*55)
    y_pred_cls = classifier.predict(X_test)
    cls_metrics = compute_classification_metrics(y_test_cls, y_pred_cls)
    print(f"  Accuracy:  {cls_metrics['accuracy']:.4f}")
    print(f"  Macro F1:  {cls_metrics['macro_f1']:.4f}")
    _plot_confusion_matrix(cls_metrics["confusion_matrix"])

    # ── Seasonal breakdown ─────────────────────────────────────
    print("\nSeasonal error breakdown:")
    _seasonal_breakdown(test_df, y_pred)

    # ── Save metrics to CSV ────────────────────────────────────
    metrics_df = pd.DataFrame([{
        "model": "XGBoost Delay Predictor",
        **metrics,
    }])
    metrics_path = OUTPUT_DIR / "metrics.csv"
    metrics_df.to_csv(metrics_path, index=False)
    print(f"\nMetrics saved: {metrics_path}")
    print(f"Plots saved:   {OUTPUT_DIR}/")
    return metrics


# ── Plot helpers ───────────────────────────────────────────────

def _plot_residuals(y_true, y_pred):
    residuals = y_pred - y_true
    plt.figure(figsize=(10, 4))
    plt.hist(residuals, bins=50, color="#003580", alpha=0.75, edgecolor="white")
    plt.axvline(0, color="#FF6B00", linestyle="--", linewidth=2, label="Zero error")
    plt.axvline(residuals.mean(), color="red", linestyle="-", linewidth=1.5,
                label=f"Mean bias: {residuals.mean():+.1f} min")
    plt.xlabel("Prediction Error (minutes)")
    plt.ylabel("Count")
    plt.title("Residual Distribution — Delay Predictor")
    plt.legend()
    plt.tight_layout()
    path = OUTPUT_DIR / "residuals.png"
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Residual plot saved: {path}")


def _plot_pred_vs_actual(y_true, y_pred):
    sample = min(2000, len(y_true))
    idx = np.random.choice(len(y_true), sample, replace=False)
    plt.figure(figsize=(8, 8))
    plt.scatter(y_true[idx], y_pred[idx], alpha=0.3, s=10, color="#003580")
    lims = [max(-30, min(y_true)), min(500, max(y_true))]
    plt.plot(lims, lims, "r--", linewidth=2, label="Perfect prediction")
    plt.xlabel("Actual Delay (min)")
    plt.ylabel("Predicted Delay (min)")
    plt.title(f"Predicted vs Actual (n={sample:,})")
    plt.legend()
    plt.tight_layout()
    path = OUTPUT_DIR / "pred_vs_actual.png"
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Pred vs actual saved: {path}")


def _plot_feature_importance(predictor: XGBoostDelayPredictor):
    importance = predictor.feature_importance()
    top15 = list(importance.items())[:15]
    features, scores = zip(*top15)

    plt.figure(figsize=(10, 6))
    bars = plt.barh(range(len(features)), scores, color="#FF6B00", alpha=0.85)
    plt.yticks(range(len(features)), [f.replace("_", " ").title() for f in features])
    plt.xlabel("Feature Importance (gain)")
    plt.title("Top 15 Features — XGBoost Delay Predictor")
    plt.gca().invert_yaxis()
    plt.tight_layout()
    path = OUTPUT_DIR / "feature_importance.png"
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Feature importance saved: {path}")


def _plot_confusion_matrix(cm: list):
    import matplotlib.colors as mcolors
    cm_array = np.array(cm)
    plt.figure(figsize=(7, 6))
    plt.imshow(cm_array, interpolation="nearest", cmap="Blues")
    plt.colorbar()
    tick_marks = range(len(DELAY_CLASSES))
    plt.xticks(tick_marks, DELAY_CLASSES, rotation=30)
    plt.yticks(tick_marks, DELAY_CLASSES)
    thresh = cm_array.max() / 2.0
    for i in range(cm_array.shape[0]):
        for j in range(cm_array.shape[1]):
            plt.text(j, i, f"{cm_array[i, j]:,}",
                     ha="center", va="center",
                     color="white" if cm_array[i, j] > thresh else "black")
    plt.ylabel("True Class")
    plt.xlabel("Predicted Class")
    plt.title("Confusion Matrix — Delay Classifier")
    plt.tight_layout()
    path = OUTPUT_DIR / "confusion_matrix.png"
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Confusion matrix saved: {path}")


def _seasonal_breakdown(test_df: pd.DataFrame, y_pred: np.ndarray):
    df_eval = test_df.copy().reset_index(drop=True)
    df_eval["y_pred"] = y_pred[:len(df_eval)]
    df_eval["abs_error"] = np.abs(df_eval["y_pred"] - df_eval["arrival_delay_minutes"])

    season_map = {
        1: "Fog",  2: "Winter",  3: "Spring",  4: "Summer", 5: "Summer",
        6: "Monsoon",  7: "Monsoon",  8: "Monsoon",  9: "Monsoon",
        10: "Harvest", 11: "Harvest", 12: "Fog",
    }
    df_eval["season"] = df_eval["month"].map(season_map)

    breakdown = df_eval.groupby("season")["abs_error"].agg(["mean", "count"]).round(2)
    breakdown.columns = ["MAE (min)", "Count"]
    print(breakdown.to_string())