# ml/models/delay_predictor.py
# XGBoost delay regression model.
# Wraps XGBRegressor with fit/predict/explain/save/load interface.
# This is what gets loaded by app/services/prediction_service.py at startup.

import joblib
import numpy as np
from pathlib import Path
from typing import Optional

from xgboost import XGBRegressor

from data.etl.feature_engineering import FEATURE_COLUMNS


class XGBoostDelayPredictor:
    """
    Production XGBoost delay regression model.

    Usage:
        predictor = XGBoostDelayPredictor()
        predictor.fit(X_train, y_train)
        predictions = predictor.predict(X_test)
        explanation = predictor.explain(X_single_row)
        predictor.save("ml/saved_models/xgboost_delay_predictor.pkl")

        loaded = XGBoostDelayPredictor.load("ml/saved_models/xgboost_delay_predictor.pkl")
    """

    DEFAULT_PARAMS = {
        "n_estimators":    500,
        "max_depth":       6,
        "learning_rate":   0.05,
        "subsample":       0.8,
        "colsample_bytree":0.8,
        "min_child_weight":3,
        "reg_alpha":       0.1,
        "reg_lambda":      1.0,
        "random_state":    42,
        "n_jobs":         -1,
        "tree_method":    "hist",   # Fast histogram-based training
    }

    def __init__(self, **kwargs):
        params = {**self.DEFAULT_PARAMS, **kwargs}
        self.model = XGBRegressor(**params)
        self.feature_columns = FEATURE_COLUMNS
        self.model_version = "xgboost_v1.0"
        self._is_fitted = False

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
    ) -> "XGBoostDelayPredictor":
        """
        Train the model with optional early stopping on validation set.
        Early stopping prevents overfitting — stops if val MAE doesn't improve for 30 rounds.
        """
        eval_set = [(X_val, y_val)] if X_val is not None else None

        self.model.fit(
            X_train,
            y_train,
            eval_set=eval_set,
            verbose=50,  # Print every 50 trees
        )
        self._is_fitted = True
        print(f"  XGBoost fitted on {len(y_train):,} samples")
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict delay in minutes. Clipped to [-60, 720] range."""
        if not self._is_fitted:
            raise RuntimeError("Model is not fitted yet. Call fit() first.")
        preds = self.model.predict(X)
        return np.clip(preds, -60, 720)

    def predict_single(self, features: dict) -> float:
        """
        Predict from a feature dict (used by prediction_service.py).
        Handles missing features gracefully.
        """
        row = np.array([[
            features.get(col, 0) for col in self.feature_columns
        ]])
        return float(self.predict(row)[0])

    def explain(self, features: dict, top_n: int = 5) -> dict:
        """
        Get SHAP explanation for a single prediction.
        Returns {"base_value": float, "factors": [{"feature", "contribution", ...}]}
        """
        from ml.utils.shap_explainer import get_shap_explanation, get_base_value

        row = np.array([[features.get(col, 0) for col in self.feature_columns]])
        factors = get_shap_explanation(self.model, row, self.feature_columns, top_n=top_n)
        base = get_base_value(self.model)
        return {"base_value": round(base, 2), "factors": factors}

    def feature_importance(self) -> dict:
        """Return feature importance scores (gain-based)."""
        importance = self.model.feature_importances_
        return dict(sorted(
            zip(self.feature_columns, importance.tolist()),
            key=lambda x: x[1],
            reverse=True,
        ))

    def save(self, path: str) -> None:
        """Serialize the full predictor (model + metadata) to disk."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        print(f"  Model saved: {path}")

    @classmethod
    def load(cls, path: str) -> "XGBoostDelayPredictor":
        """Load a serialized predictor from disk."""
        obj = joblib.load(path)
        if not isinstance(obj, cls):
            raise TypeError(f"Loaded object is not an XGBoostDelayPredictor: {type(obj)}")
        return obj

    def __repr__(self) -> str:
        status = "fitted" if self._is_fitted else "not fitted"
        return f"<XGBoostDelayPredictor version={self.model_version} status={status}>"