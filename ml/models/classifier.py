# ml/models/classifier.py
# 4-class delay classification: ON_TIME / SLIGHT / MODERATE / SEVERE
# Used alongside the regression model to give probability estimates per class.

import joblib
import numpy as np
from pathlib import Path
from typing import Optional

from xgboost import XGBClassifier

from data.etl.feature_engineering import FEATURE_COLUMNS

DELAY_CLASSES = ["ON_TIME", "SLIGHT", "MODERATE", "SEVERE"]
CLASS_TO_INT  = {c: i for i, c in enumerate(DELAY_CLASSES)}
INT_TO_CLASS  = {i: c for i, c in enumerate(DELAY_CLASSES)}


class DelayClassifier:
    """
    Multiclass XGBoost classifier predicting delay severity bucket.

    Outputs:
        - Predicted class label (ON_TIME, SLIGHT, MODERATE, SEVERE)
        - Class probabilities for all 4 classes
    """

    DEFAULT_PARAMS = {
        "n_estimators":     400,
        "max_depth":        5,
        "learning_rate":    0.05,
        "subsample":        0.8,
        "colsample_bytree": 0.8,
        "use_label_encoder":False,
        "eval_metric":      "mlogloss",
        "random_state":     42,
        "n_jobs":          -1,
        "num_class":        4,
        "objective":        "multi:softprob",
    }

    def __init__(self, **kwargs):
        params = {**self.DEFAULT_PARAMS, **kwargs}
        self.model = XGBClassifier(**params)
        self.feature_columns = FEATURE_COLUMNS
        self._is_fitted = False

    def fit(
        self,
        X_train: np.ndarray,
        y_train_labels: list[str],
        X_val: Optional[np.ndarray] = None,
        y_val_labels: Optional[list[str]] = None,
    ) -> "DelayClassifier":
        """
        y_train_labels: list of strings like ["ON_TIME", "SLIGHT", ...]
        Converts to integer encoding internally.
        """
        y_train = np.array([CLASS_TO_INT[c] for c in y_train_labels])

        eval_set = None
        if X_val is not None and y_val_labels is not None:
            y_val = np.array([CLASS_TO_INT[c] for c in y_val_labels])
            eval_set = [(X_val, y_val)]

        self.model.fit(X_train, y_train, eval_set=eval_set, verbose=50)
        self._is_fitted = True
        print(f"  Classifier fitted on {len(y_train):,} samples")
        return self

    def predict(self, X: np.ndarray) -> list[str]:
        """Return predicted class labels."""
        int_preds = self.model.predict(X)
        return [INT_TO_CLASS[i] for i in int_preds]

    def predict_proba_dict(self, features: dict) -> dict[str, float]:
        """
        Return class probabilities as a dict for a single feature row.
        Used by prediction_service.py to populate class_probabilities in API response.
        """
        row = np.array([[features.get(col, 0) for col in self.feature_columns]])
        proba = self.model.predict_proba(row)[0]
        return {cls: round(float(proba[i]), 4) for i, cls in enumerate(DELAY_CLASSES)}

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        print(f"  Classifier saved: {path}")

    @classmethod
    def load(cls, path: str) -> "DelayClassifier":
        return joblib.load(path)

    def __repr__(self) -> str:
        status = "fitted" if self._is_fitted else "not fitted"
        return f"<DelayClassifier classes={DELAY_CLASSES} status={status}>"