# data/etl/clean.py
# Raw CSV → cleaned DataFrame.
# Called by ingest.py before loading into PostgreSQL.
#
# Handles the most common Indian Railways Kaggle dataset formats.
# Robust to missing columns, bad encoding, and extreme values.

import re
import numpy as np
import pandas as pd
from pathlib import Path


# ── Column name normalisation ──────────────────────────────────
# Different Kaggle datasets use different column names.
# Map all variants to a standard name.

COLUMN_MAP = {
    # Train identifiers
    "train no":           "train_number",
    "train_no":           "train_number",
    "trainno":            "train_number",
    "train number":       "train_number",
    "train_number":       "train_number",

    # Train name
    "train name":         "train_name",
    "train_name":         "train_name",
    "trainname":          "train_name",

    # Station code
    "station code":       "station_code",
    "station_code":       "station_code",
    "stationcode":        "station_code",
    "stn_code":           "station_code",
    "stn code":           "station_code",

    # Station name
    "station name":       "station_name",
    "station_name":       "station_name",
    "stationname":        "station_name",

    # Origin / Destination
    "from station":       "origin_code",
    "from_station":       "origin_code",
    "source":             "origin_code",
    "origin":             "origin_code",
    "to station":         "destination_code",
    "to_station":         "destination_code",
    "destination":        "destination_code",

    # Date
    "date":               "journey_date",
    "journey_date":       "journey_date",
    "run_date":           "journey_date",

    # Scheduled times
    "sch_arr":            "scheduled_arrival",
    "scheduled arrival":  "scheduled_arrival",
    "arr":                "scheduled_arrival",
    "sch_dep":            "scheduled_departure",
    "scheduled departure":"scheduled_departure",
    "dep":                "scheduled_departure",

    # Actual times
    "actual arrival":     "actual_arrival",
    "actual_arrival":     "actual_arrival",
    "actual departure":   "actual_departure",
    "actual_departure":   "actual_departure",

    # Delay
    "delay":              "arrival_delay_minutes",
    "delay_minutes":      "arrival_delay_minutes",
    "arr_delay":          "arrival_delay_minutes",
    "arrival delay":      "arrival_delay_minutes",
    "arrival_delay":      "arrival_delay_minutes",

    # Category
    "train type":         "category",
    "train_type":         "category",
    "type":               "category",
    "category":           "category",

    # Zone
    "zone":               "zone",
}

# Valid Indian Railway zone codes
VALID_ZONES = {
    "NR", "SR", "CR", "ER", "WR", "NER", "ECR", "SCR",
    "SER", "NCR", "NWR", "WCR", "NFR", "ECOR", "SWR", "SECR", "KR",
}

# Train category normalisation
CATEGORY_MAP = {
    "raj":        "Rajdhani",
    "rajdhani":   "Rajdhani",
    "shatabdi":   "Shatabdi",
    "sht":        "Shatabdi",
    "duronto":    "Duronto",
    "dur":        "Duronto",
    "superfast":  "Superfast",
    "sf":         "Superfast",
    "mail":       "Mail",
    "express":    "Express",
    "exp":        "Express",
    "passenger":  "Passenger",
    "pass":       "Passenger",
    "memu":       "MEMU",
    "emu":        "EMU",
    "demu":       "Passenger",
}


# ── Main cleaning function ─────────────────────────────────────

def clean_delay_records(df: pd.DataFrame) -> pd.DataFrame:
    """
    Full cleaning pipeline for raw delay records CSV.
    Returns a DataFrame ready for database ingestion.

    Steps:
    1. Normalise column names
    2. Clean station codes and train numbers
    3. Parse and validate dates
    4. Handle delay values (nulls, negatives, extremes)
    5. Normalise train categories
    6. Drop duplicates
    """
    df = df.copy()

    # ── Step 1: Normalise column names ─────────────────────────
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.rename(columns=COLUMN_MAP)

    # ── Step 2: Station codes ──────────────────────────────────
    if "station_code" in df.columns:
        df["station_code"] = (
            df["station_code"]
            .astype(str)
            .str.strip()
            .str.upper()
            .str.replace(r"[^A-Z0-9]", "", regex=True)
        )
        # Drop rows with no station code
        df = df[df["station_code"].str.len() > 0]
        df = df[df["station_code"] != "NAN"]

    # ── Step 3: Train numbers ──────────────────────────────────
    if "train_number" in df.columns:
        df["train_number"] = (
            df["train_number"]
            .astype(str)
            .str.strip()
            .str.extract(r"(\d{4,5})", expand=False)  # Extract 4-5 digit number
        )
        df = df[df["train_number"].notna()]

    # ── Step 4: Dates ──────────────────────────────────────────
    if "journey_date" in df.columns:
        df["journey_date"] = pd.to_datetime(
            df["journey_date"], errors="coerce", dayfirst=True
        )
        # Drop rows where date couldn't be parsed
        df = df[df["journey_date"].notna()]
        # Drop future dates (data quality issue)
        df = df[df["journey_date"] <= pd.Timestamp.now()]
        df["journey_date"] = df["journey_date"].dt.date

    # ── Step 5: Delay values ───────────────────────────────────
    if "arrival_delay_minutes" in df.columns:
        df["arrival_delay_minutes"] = pd.to_numeric(
            df["arrival_delay_minutes"], errors="coerce"
        )
        # Indian Railways: cap at 720 min (12 hours) — beyond this is likely bad data
        df["arrival_delay_minutes"] = df["arrival_delay_minutes"].clip(lower=-60, upper=720)
        # Keep rows where delay is missing (we can still store the schedule data)
    else:
        df["arrival_delay_minutes"] = np.nan

    if "departure_delay_minutes" not in df.columns:
        df["departure_delay_minutes"] = np.nan

    # ── Step 6: Train category normalisation ───────────────────
    if "category" in df.columns:
        df["category"] = df["category"].astype(str).str.strip().str.lower()
        df["category"] = df["category"].map(
            lambda x: next(
                (v for k, v in CATEGORY_MAP.items() if k in x),
                "Express",   # Default
            )
        )
    else:
        df["category"] = "Express"

    # ── Step 7: Zone cleanup ───────────────────────────────────
    if "zone" in df.columns:
        df["zone"] = df["zone"].astype(str).str.strip().str.upper()
        df.loc[~df["zone"].isin(VALID_ZONES), "zone"] = None
    else:
        df["zone"] = None

    # ── Step 8: Drop exact duplicates ─────────────────────────
    subset_cols = [c for c in ["train_number", "station_code", "journey_date"] if c in df.columns]
    if subset_cols:
        before = len(df)
        df = df.drop_duplicates(subset=subset_cols, keep="last")
        dropped = before - len(df)
        if dropped > 0:
            print(f"  Dropped {dropped:,} duplicate rows")

    # ── Step 9: Fill missing text fields ──────────────────────
    for col in ["train_name", "station_name", "origin_code", "destination_code"]:
        if col not in df.columns:
            df[col] = None

    for col in ["reason_code", "weather_condition"]:
        if col not in df.columns:
            df[col] = None

    df["data_source"] = "historical"
    df["is_cancelled"] = False

    print(f"  Cleaned: {len(df):,} records ready for ingestion")
    return df


def clean_stations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean a stations reference CSV.
    Expected columns: station_code, name, zone, latitude, longitude
    """
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    if "station_code" in df.columns:
        df["station_code"] = df["station_code"].astype(str).str.strip().str.upper()

    if "name" in df.columns:
        df["name"] = df["name"].astype(str).str.strip().str.title()

    if "zone" in df.columns:
        df["zone"] = df["zone"].astype(str).str.strip().str.upper()
        df.loc[~df["zone"].isin(VALID_ZONES), "zone"] = None

    for coord in ["latitude", "longitude"]:
        if coord in df.columns:
            df[coord] = pd.to_numeric(df[coord], errors="coerce")

    df = df[df["station_code"].notna() & (df["station_code"] != "")]
    df = df.drop_duplicates(subset=["station_code"], keep="last")
    return df


def validate_dataframe(df: pd.DataFrame, required_cols: list[str]) -> list[str]:
    """
    Check a cleaned DataFrame has required columns.
    Returns a list of error messages (empty if all OK).
    """
    errors = []
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        errors.append(f"Missing required columns: {missing}")
    if len(df) == 0:
        errors.append("DataFrame is empty after cleaning")
    return errors


def infer_zone_from_station_code(station_code: str) -> str | None:
    """
    Heuristic: infer railway zone from station code prefix.
    Only used when zone column is absent from source data.
    """
    prefix_map = {
        "ND":  "NR",   # New Delhi stations
        "MB":  "WR",   # Mumbai stations
        "MS":  "SR",   # Madras/Chennai
        "HW":  "NR",   # Haridwar zone
        "CNB": "NCR",  # Kanpur
        "ALD": "NCR",  # Allahabad
        "BSB": "NER",  # Varanasi
    }
    for prefix, zone in prefix_map.items():
        if station_code.startswith(prefix):
            return zone
    return None