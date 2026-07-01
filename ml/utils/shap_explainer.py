# ml/utils/shap_explainer.py
# Wraps SHAP for easy use in prediction_service.py and evaluation_pipeline.py.
# TreeExplainer is fast (<5ms) for XGBoost — safe for real-time API use.

import numpy as np
import pandas as pd

FEATURE_DISPLAY_NAMES = {
    "month":           "Month of Year",
    "day_of_week":     "Day of Week",
    "quarter":         "Quarter",
    "week_of_year":    "Week of Year",
    "day_of_month":    "Day of Month",
    "is_monsoon":      "Monsoon Season (Jun–Sep)",
    "is_fog_season":   "Fog Season (Dec–Jan)",
    "is_summer_peak":  "Summer Peak (Apr–May)",
    "is_harvest_fest": "Harvest Festival Season",
    "is_weekend":      "Weekend",
    "is_holiday_week": "Near Indian Holiday",
    "category_rank":   "Train Category",
    "zone_NR":         "Northern Railway Zone",
    "zone_SR":         "Southern Railway Zone",
    "zone_CR":         "Central Railway Zone",
    "zone_ER":         "Eastern Railway Zone",
    "zone_WR":         "Western Railway Zone",
    "zone_NCR":        "North Central Railway Zone",
    "hist_delay_7d":   "7-Day Historical Avg Delay",
    "hist_delay_30d":  "30-Day Historical Avg Delay",
    "route_avg_delay": "Route Historical Avg Delay",
    "zone_month_avg":  "Zone-Month Historical Avg",
}


def get_shap_explanation(
    model,
    X: np.ndarray,
    feature_names: list[str],
    top_n: int = 5,
) -> list[dict]:
    """
    Compute SHAP values for a single prediction row.
    Returns top_n features sorted by absolute contribution.

    Args:
        model:         Fitted XGBoost or sklearn model
        X:             Single row as (1, n_features) numpy array
        feature_names: List of feature column names
        top_n:         Number of top features to return

    Returns:
        [{"feature": str, "contribution_minutes": float, "direction": "+/-",
          "display_name": str}, ...]
    """
    import shap

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    if X.ndim == 1:
        X = X.reshape(1, -1)

    sv = shap_values[0] if shap_values.ndim > 1 else shap_values

    # Sort by absolute value descending
    top_indices = np.argsort(np.abs(sv))[::-1][:top_n]

    results = []
    for i in top_indices:
        contribution = float(sv[i])
        fname = feature_names[i] if i < len(feature_names) else f"feature_{i}"
        results.append({
            "feature":               fname,
            "contribution_minutes":  round(contribution, 2),
            "direction":             "+" if contribution >= 0 else "-",
            "display_name":          FEATURE_DISPLAY_NAMES.get(fname, fname.replace("_", " ").title()),
        })

    return results


def get_base_value(model) -> float:
    """Return the model's expected value (base SHAP value)."""
    import shap
    explainer = shap.TreeExplainer(model)
    ev = explainer.expected_value
    return float(ev[0] if isinstance(ev, (list, np.ndarray)) else ev)


def generate_shap_summary(
    model,
    X_test: np.ndarray,
    feature_names: list[str],
    output_path: str = "ml/saved_models/shap_summary.png",
) -> None:
    """
    Generate and save a SHAP summary (beeswarm) plot.
    Called by evaluation_pipeline.py — saved to disk for reporting.
    """
    import shap
    import matplotlib.pyplot as plt
    from pathlib import Path

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    explainer  = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test)

    plt.figure(figsize=(10, 6))
    shap.summary_plot(
        shap_values,
        X_test,
        feature_names=feature_names,
        show=False,
        max_display=15,
    )
    plt.title("SHAP Feature Importance — Delay Predictor")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  SHAP summary saved: {output_path}")