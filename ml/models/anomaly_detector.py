# ml/models/anomaly_detector.py
# Two-stage anomaly detection:
#   Stage 1: Isolation Forest flags statistically unusual delay records
#   Stage 2: Z-score filter removes false positives on structurally late routes
#
# Why two stages? Some routes are ALWAYS late in monsoon season.
# Isolation Forest would call them "normal" because they're consistent.
# The Z-score stage flags records that are unusual vs THEIR OWN baseline.

import joblib
import numpy as np
import pandas as pd
from pathlib import Path

from sklearn.ensemble import IsolationForest

from data.etl.feature_engineering import FEATURE_COLUMNS

ANOMALY_FEATURE_COLS = FEATURE_COLUMNS + [
    "arrival_delay_minutes",    # Raw delay is a signal
]

SEVERITY_THRESHOLDS = {
    "CRITICAL": 4.0,
    "HIGH":     3.0,
    "MEDIUM":   2.0,
    "LOW":      1.5,
}


class AnomalyDetector:
    """
    Production anomaly detector for Indian Railways delay records.

    Two-stage pipeline:
    1. IsolationForest: scores each record based on feature-space density
    2. Z-score gate:    flags records >= 2 std devs above their route-month baseline
    """

    def __init__(
        self,
        contamination: float = 0.05,    # Expect ~5% of records to be anomalous
        n_estimators: int = 200,
        max_features: float = 0.8,
        z_score_threshold: float = 2.0,
    ):
        self.isolation_forest = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            max_features=max_features,
            random_state=42,
            n_jobs=-1,
        )
        self.z_score_threshold = z_score_threshold
        self._is_fitted = False
        self._route_month_stats: dict | None = None

    def _build_route_month_stats(self, df: pd.DataFrame) -> dict:
        """
        Pre-compute per-(train, month) mean and std of arrival delay.
        Used in Stage 2 Z-score calculation.
        """
        stats = {}
        for (train_num, month), group in df.groupby(["train_number", "month"]):
            delays = group["arrival_delay_minutes"].dropna()
            if len(delays) >= 5:  # Need at least 5 records to compute meaningful stats
                stats[(train_num, month)] = {
                    "mean": delays.mean(),
                    "std":  max(delays.std(), 1.0),  # Avoid division by zero
                }
        return stats

    def fit(self, df: pd.DataFrame) -> "AnomalyDetector":
        """
        Fit the detector on historical delay records.

        Args:
            df: DataFrame with FEATURE_COLUMNS + train_number + month + arrival_delay_minutes
        """
        # Build route-month baseline for Z-score stage
        self._route_month_stats = self._build_route_month_stats(df)

        # Prepare feature matrix
        available_cols = [c for c in ANOMALY_FEATURE_COLS if c in df.columns]
        X = df[available_cols].fillna(0).values

        self.isolation_forest.fit(X)
        self._is_fitted = True
        print(f"  AnomalyDetector fitted on {len(df):,} records")
        print(f"  Route-month baselines: {len(self._route_month_stats)} (train, month) pairs")
        return self

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect anomalies in a DataFrame of delay records.
        Returns the input DataFrame with added columns:
            if_score, z_score, is_anomaly, severity, anomaly_type
        """
        df = df.copy()
        available_cols = [c for c in ANOMALY_FEATURE_COLS if c in df.columns]
        X = df[available_cols].fillna(0).values

        # Stage 1: Isolation Forest scores
        df["if_score"]      = self.isolation_forest.score_samples(X)
        df["is_if_anomaly"] = self.isolation_forest.predict(X) == -1

        # Stage 2: Z-score vs route-month baseline
        df["z_score"] = df.apply(self._compute_z_score, axis=1)

        # Combined: must trigger BOTH stages to be flagged
        df["is_anomaly"] = df["is_if_anomaly"] & (df["z_score"] >= self.z_score_threshold)

        # Severity based on Z-score magnitude
        df["severity"] = df["z_score"].apply(self._classify_severity)
        df.loc[~df["is_anomaly"], "severity"] = None

        # Anomaly type classification
        df["anomaly_type"] = df.apply(self._classify_type, axis=1)
        df.loc[~df["is_anomaly"], "anomaly_type"] = None

        n_anomalies = df["is_anomaly"].sum()
        pct = n_anomalies / len(df) * 100
        print(f"  Detected {n_anomalies:,} anomalies ({pct:.1f}% of records)")
        return df

    def score_single(self, features: dict) -> dict:
        """
        Score a single record for anomaly detection.
        Used by the API to flag high-risk predictions.
        """
        row = np.array([[features.get(col, 0) for col in ANOMALY_FEATURE_COLS
                         if col in features]])
        if_score = float(self.isolation_forest.score_samples(row.reshape(1, -1))[0])
        is_anomaly = if_score < -0.1   # Heuristic threshold for single records
        return {
            "is_anomaly":   is_anomaly,
            "anomaly_score":round(if_score, 4),
            "severity":     "HIGH" if if_score < -0.2 else "MEDIUM" if is_anomaly else None,
        }

    def _compute_z_score(self, row: pd.Series) -> float:
        """How many std devs is this delay above its route-month baseline?"""
        key = (
            row.get("train_number", ""),
            int(row.get("month", 1)),
        )
        stats = self._route_month_stats.get(key) if self._route_month_stats else None
        if stats is None:
            return 0.0
        delay = row.get("arrival_delay_minutes", 0) or 0
        return max(0.0, (delay - stats["mean"]) / stats["std"])

    @staticmethod
    def _classify_severity(z_score: float) -> str | None:
        if z_score >= SEVERITY_THRESHOLDS["CRITICAL"]: return "CRITICAL"
        if z_score >= SEVERITY_THRESHOLDS["HIGH"]:     return "HIGH"
        if z_score >= SEVERITY_THRESHOLDS["MEDIUM"]:   return "MEDIUM"
        if z_score >= SEVERITY_THRESHOLDS["LOW"]:      return "LOW"
        return None

    @staticmethod
    def _classify_type(row: pd.Series) -> str | None:
        if not row.get("is_anomaly"):
            return None
        delay = row.get("arrival_delay_minutes", 0) or 0
        if delay < -15:   return "EARLY_DEPARTURE"
        if delay > 240:   return "EXTREME_DELAY"
        return "ROUTE_DISRUPTION"

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        print(f"  AnomalyDetector saved: {path}")

    @classmethod
    def load(cls, path: str) -> "AnomalyDetector":
        return joblib.load(path)