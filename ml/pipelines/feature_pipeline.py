# ml/pipelines/feature_pipeline.py
# Loads delay records from PostgreSQL and produces the ML feature matrix.
# Bridge between the DB and training_pipeline.py.

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from data.etl.feature_engineering import (
    FEATURE_COLUMNS,
    TARGET_CLASSIFICATION,
    TARGET_REGRESSION,
    engineer_features,
    temporal_train_test_split,
    validate_features,
)


def load_from_db(
    min_records: int = 1_000,
    limit: int = 500_000,
) -> pd.DataFrame:
    """
    Load delay records from PostgreSQL and apply feature engineering.
    Returns the full feature-engineered DataFrame.

    Args:
        min_records: Raise if fewer records found (likely empty DB)
        limit:       Max rows to load (memory guard)
    """
    from app.core.database import SessionLocal
    from sqlalchemy import text

    print(f"Loading delay records from database (limit={limit:,})...")

    query = text(f"""
        SELECT
            dr.journey_date,
            dr.arrival_delay_minutes,
            dr.departure_delay_minutes,
            dr.reason_code,
            dr.weather_condition,
            dr.is_cancelled,
            t.train_number,
            t.category,
            t.zone,
            t.distance_km,
            t.total_stops,
            s.station_code,
            s.name AS station_name
        FROM delay_records dr
        JOIN trains t ON dr.train_id = t.id
        JOIN stations s ON dr.station_id = s.id
        WHERE dr.is_cancelled = FALSE
          AND dr.arrival_delay_minutes IS NOT NULL
        ORDER BY dr.journey_date DESC
        LIMIT {limit}
    """)

    with SessionLocal() as db:
        result = db.execute(query)
        rows = result.fetchall()
        cols = result.keys()

    df = pd.DataFrame(rows, columns=list(cols))
    print(f"  Loaded {len(df):,} records from database")

    if len(df) < min_records:
        raise ValueError(
            f"Only {len(df)} records found. Need at least {min_records}. "
            f"Run: python data/etl/ingest.py --generate-synthetic"
        )

    return df


def load_from_csv(csv_path: str) -> pd.DataFrame:
    """Load from a CSV file (for testing without a DB connection)."""
    print(f"Loading from CSV: {csv_path}")
    try:
        df = pd.read_csv(csv_path, encoding="utf-8", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding="latin-1", low_memory=False)
    print(f"  Loaded {len(df):,} raw rows")
    return df


def prepare_features(
    df: pd.DataFrame,
    test_months: int = 3,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str], list[str]]:
    """
    Full feature preparation pipeline:
    1. Apply feature engineering
    2. Validate features
    3. Temporal train/test split
    4. Return (X_train, X_test, y_train, y_test, feature_cols, class_labels)

    Returns:
        X_train, X_test  — feature matrices
        y_train, y_test  — regression targets (delay minutes)
        y_train_cls, y_test_cls — classification targets (class labels)
    """
    print("\nApplying feature engineering...")
    df_feat = engineer_features(df)

    errors = validate_features(df_feat)
    if errors:
        raise ValueError(f"Feature validation failed: {errors}")

    print(f"  Features: {len(FEATURE_COLUMNS)} columns")
    print(f"  Samples:  {len(df_feat):,}")
    print(f"  Target mean delay: {df_feat[TARGET_REGRESSION].mean():.1f} min")

    # Temporal split — NEVER random split for time series
    train_df, test_df = temporal_train_test_split(df_feat, test_months=test_months)

    X_train = train_df[FEATURE_COLUMNS].fillna(0).values
    X_test  = test_df[FEATURE_COLUMNS].fillna(0).values
    y_train = train_df[TARGET_REGRESSION].values
    y_test  = test_df[TARGET_REGRESSION].values
    y_train_cls = train_df[TARGET_CLASSIFICATION].tolist()
    y_test_cls  = test_df[TARGET_CLASSIFICATION].tolist()

    print(f"\nSplit complete:")
    print(f"  Train: {len(X_train):,} rows")
    print(f"  Test:  {len(X_test):,}  rows")

    return X_train, X_test, y_train, y_test, y_train_cls, y_test_cls, train_df, test_df