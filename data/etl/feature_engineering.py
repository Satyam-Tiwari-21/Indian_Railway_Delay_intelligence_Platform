# data/etl/feature_engineering.py
# Builds the ML feature matrix from raw delay records.
# Used by BOTH:
#   1. ml/pipelines/training_pipeline.py  — offline model training
#   2. app/services/prediction_service.py — live API inference
#
# Keeping feature logic in ONE place guarantees training/serving consistency.
# (Training-serving skew is the #1 source of ML bugs in production.)

from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd


# ── Indian holidays calendar ───────────────────────────────────
# Approximate dates — covers major national holidays that spike train traffic

INDIAN_HOLIDAYS: dict[str, list[tuple[int, int]]] = {
    "Republic Day":    [(1, 26)],
    "Holi":            [(3, 14), (3, 25), (3, 6)],      # Varies year to year
    "Ram Navami":      [(4, 2), (4, 21)],
    "Eid al-Fitr":     [(4, 10), (4, 30), (3, 31)],
    "Eid al-Adha":     [(6, 17), (7, 7), (6, 28)],
    "Independence":    [(8, 15)],
    "Onam":            [(8, 30), (9, 8)],
    "Navratri Start":  [(10, 3), (10, 22), (10, 13)],
    "Dussehra":        [(10, 12), (10, 24), (10, 15)],
    "Diwali":          [(11, 1), (10, 21), (11, 12)],
    "Chhath Puja":     [(11, 3), (10, 23)],
    "Guru Nanak":      [(11, 19), (11, 8)],
    "Christmas":       [(12, 25)],
    "New Year Eve":    [(12, 31)],
}


def is_near_indian_holiday(journey_date: date, window_days: int = 3) -> bool:
    """
    Returns True if the date is within `window_days` of a major Indian holiday.
    Train traffic surges 3-4 days before/after major holidays.
    """
    for holiday_name, occurrences in INDIAN_HOLIDAYS.items():
        for month, day in occurrences:
            try:
                holiday = journey_date.replace(month=month, day=day)
                if abs((journey_date - holiday).days) <= window_days:
                    return True
            except ValueError:
                continue  # Invalid date (e.g., Feb 30)
    return False


def get_delay_category(delay_minutes: float) -> str:
    """
    Classify delay into operational buckets.
    Used as target variable for classification model.
    """
    if delay_minutes <= 5:   return "ON_TIME"
    if delay_minutes <= 30:  return "SLIGHT"
    if delay_minutes <= 120: return "MODERATE"
    return "SEVERE"


# ── Main feature engineering function ─────────────────────────

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build the complete ML feature matrix from cleaned delay records.
    Adds ~20 features. Drops rows with missing target variable.

    Input DataFrame must have at minimum:
        journey_date, train_number, station_code, category, zone,
        arrival_delay_minutes (target)

    Returns a DataFrame with all features + target column.
    """
    df = df.copy()

    # Ensure journey_date is datetime
    if not pd.api.types.is_datetime64_any_dtype(df["journey_date"]):
        df["journey_date"] = pd.to_datetime(df["journey_date"])

    # ── Temporal features ──────────────────────────────────────
    df["month"]        = df["journey_date"].dt.month
    df["day_of_week"]  = df["journey_date"].dt.dayofweek   # 0=Mon, 6=Sun
    df["quarter"]      = df["journey_date"].dt.quarter
    df["week_of_year"] = df["journey_date"].dt.isocalendar().week.astype(int)
    df["day_of_month"] = df["journey_date"].dt.day

    # ── India seasonal features (most important for this domain) ──
    df["is_monsoon"]     = df["month"].isin([6, 7, 8, 9]).astype(int)
    df["is_fog_season"]  = df["month"].isin([12, 1]).astype(int)
    df["is_summer_peak"] = df["month"].isin([4, 5]).astype(int)   # School vacation rush
    df["is_harvest_fest"]= df["month"].isin([10, 11]).astype(int) # Navratri, Diwali
    df["is_weekend"]     = (df["day_of_week"] >= 5).astype(int)

    df["is_holiday_week"] = df["journey_date"].apply(
        lambda d: int(is_near_indian_holiday(d.date() if hasattr(d, "date") else d))
    )

    # ── Train category features ────────────────────────────────
    # Ordinal encoding: higher number = typically more delay-prone
    CATEGORY_RANK = {
        "Rajdhani": 1, "Shatabdi": 2, "Duronto": 2,
        "Superfast": 3, "Mail": 4, "Express": 4, "Passenger": 5,
        "MEMU": 3, "EMU": 3,
    }
    df["category_rank"] = df["category"].map(CATEGORY_RANK).fillna(3)

    # One-hot encode zone (top zones)
    TOP_ZONES = ["NR", "SR", "CR", "ER", "WR", "NCR"]
    for zone in TOP_ZONES:
        df[f"zone_{zone}"] = (df["zone"] == zone).astype(int)

    # ── Historical lag features (most predictive features) ─────
    # These capture the "structural" delay of each train/station pair.
    # Sort first so rolling windows work correctly.
    df = df.sort_values(["train_number", "journey_date"]).reset_index(drop=True)

    # Group by train — compute rolling avg delays
    df["hist_delay_7d"]  = (
        df.groupby("train_number")["arrival_delay_minutes"]
        .transform(lambda x: x.shift(1).rolling(7,  min_periods=1).mean())
    )
    df["hist_delay_30d"] = (
        df.groupby("train_number")["arrival_delay_minutes"]
        .transform(lambda x: x.shift(1).rolling(30, min_periods=1).mean())
    )

    # Route-level average delay (train + station pair)
    route_avg = (
        df.groupby(["train_number", "station_code"])["arrival_delay_minutes"]
        .mean()
        .reset_index()
        .rename(columns={"arrival_delay_minutes": "route_avg_delay"})
    )
    df = df.merge(route_avg, on=["train_number", "station_code"], how="left")

    # Zone + month interaction — e.g., NR in Jan has fog-specific patterns
    zone_month_avg = (
        df.groupby(["zone", "month"])["arrival_delay_minutes"]
        .mean()
        .reset_index()
        .rename(columns={"arrival_delay_minutes": "zone_month_avg"})
    )
    df = df.merge(zone_month_avg, on=["zone", "month"], how="left")

    # Fill NaNs in lag features with global mean
    lag_cols = ["hist_delay_7d", "hist_delay_30d", "route_avg_delay", "zone_month_avg"]
    global_mean = df["arrival_delay_minutes"].mean()
    for col in lag_cols:
        df[col] = df[col].fillna(global_mean)

    # ── Target variable ────────────────────────────────────────
    # Regression target
    df = df[df["arrival_delay_minutes"].notna()]

    # Classification target
    df["delay_class"] = df["arrival_delay_minutes"].apply(get_delay_category)

    return df


# ── Feature column list (used by model training + serving) ────

FEATURE_COLUMNS = [
    # Temporal
    "month", "day_of_week", "quarter", "week_of_year", "day_of_month",
    # Seasonal
    "is_monsoon", "is_fog_season", "is_summer_peak", "is_harvest_fest",
    "is_weekend", "is_holiday_week",
    # Train
    "category_rank",
    # Zone one-hot
    "zone_NR", "zone_SR", "zone_CR", "zone_ER", "zone_WR", "zone_NCR",
    # Historical lag
    "hist_delay_7d", "hist_delay_30d", "route_avg_delay", "zone_month_avg",
]

TARGET_REGRESSION     = "arrival_delay_minutes"
TARGET_CLASSIFICATION = "delay_class"


# ── Train/test split helper ────────────────────────────────────

def temporal_train_test_split(
    df: pd.DataFrame,
    test_months: int = 3,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Time-based split — test set is the most recent N months.
    NEVER use random split for time series: it causes data leakage.
    """
    cutoff = df["journey_date"].max() - pd.DateOffset(months=test_months)
    train = df[df["journey_date"] <= cutoff].copy()
    test  = df[df["journey_date"] >  cutoff].copy()
    print(f"Train: {len(train):,} rows | Test: {len(test):,} rows | Cutoff: {cutoff.date()}")
    return train, test


# ── Quick validation ───────────────────────────────────────────

def validate_features(df: pd.DataFrame) -> list[str]:
    """Check that all expected feature columns are present and have no all-null columns."""
    errors = []
    missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing:
        errors.append(f"Missing feature columns: {missing}")
    for col in FEATURE_COLUMNS:
        if col in df.columns and df[col].isna().all():
            errors.append(f"Column '{col}' is entirely NaN")
    return errors


if __name__ == "__main__":
    # Quick smoke test with synthetic data
    print("Running feature engineering smoke test...")
    from data.etl.ingest import generate_synthetic_data  # type: ignore
    df_raw = generate_synthetic_data(n_rows=5_000)
    df_feat = engineer_features(df_raw)
    errors = validate_features(df_feat)
    if errors:
        print(f"❌ Validation errors: {errors}")
    else:
        print(f"✅ Feature engineering OK — {len(df_feat):,} rows, {len(FEATURE_COLUMNS)} features")
        print(f"   Columns: {list(df_feat.columns)}")