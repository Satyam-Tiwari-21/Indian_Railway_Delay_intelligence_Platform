# ml/pipelines/detect_and_persist_anomalies.py
#
# The missing link between the trained Isolation Forest model and the
# `anomalies` table that /api/v1/anomalies/feed reads from.
#
# training_pipeline.py trains AnomalyDetector and pickles it to disk, but
# never writes a single Anomaly row to the database — it only runs
# detector.detect() on the test split to print a count for evaluation.
# This script is the batch job that actually populates the anomalies table
# so the API/dashboard have something to show.
#
# Run after training:
#   python ml/pipelines/detect_and_persist_anomalies.py
#   python ml/pipelines/detect_and_persist_anomalies.py --days 90 --limit 200000
#
# Intended to be re-run periodically (cron / Task Scheduler / Admin "retrain"
# trigger) — it skips delay_records that already have an anomaly row, so
# re-running is safe and incremental rather than duplicating rows.

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
from sqlalchemy import text

from app.core.database import SessionLocal
from app.core.logging_config import setup_logging, get_logger
from app.models.db.anomaly import Anomaly
from data.etl.feature_engineering import engineer_features

setup_logging()
logger = get_logger(__name__)

MODEL_PATH = Path("ml/saved_models/anomaly_detector.pkl")

# Short, human-readable explanation per anomaly_type — shown in the
# dashboard's anomaly feed / AnomalyOut.explanation field.
_EXPLANATIONS = {
    "EARLY_DEPARTURE":  "Train departed unusually early vs. its own route/month baseline.",
    "EXTREME_DELAY":    "Delay is far beyond what this route/season normally sees.",
    "ROUTE_DISRUPTION": "Delay is statistically unusual for this train, given its history.",
}


def _load_candidate_records(days: int, limit: int) -> pd.DataFrame:
    """
    Pull recent delay records (with the raw FK ids we need to persist
    anomalies against) that haven't been scored yet.
    """
    cutoff = date.today() - timedelta(days=days)
    query = text(
        """
        SELECT
            dr.id               AS delay_record_id,
            dr.train_id,
            dr.station_id,
            dr.journey_date,
            dr.arrival_delay_minutes,
            dr.departure_delay_minutes,
            dr.reason_code,
            dr.weather_condition,
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
          AND dr.journey_date >= :cutoff
          AND NOT EXISTS (
              SELECT 1 FROM anomalies a WHERE a.delay_record_id = dr.id
          )
        ORDER BY dr.journey_date DESC
        LIMIT :limit
        """
    )
    with SessionLocal() as db:
        rows = db.execute(query, {"cutoff": cutoff, "limit": limit}).mappings().all()
    return pd.DataFrame(rows)


def run(days: int = 180, limit: int = 300_000, batch_size: int = 2_000) -> int:
    if not MODEL_PATH.exists():
        print(f"\n❌ No trained anomaly detector found at {MODEL_PATH}")
        print("   Run `python ml/train.py --model all` (or --model anomaly) first.\n")
        sys.exit(1)

    from ml.models.anomaly_detector import AnomalyDetector

    print(f"Loading anomaly detector from {MODEL_PATH} ...")
    detector = AnomalyDetector.load(str(MODEL_PATH))

    print(f"Loading un-scored delay records from the last {days} days (limit={limit:,}) ...")
    df = _load_candidate_records(days=days, limit=limit)
    if df.empty:
        print("Nothing to score — every recent record already has an anomaly verdict.")
        return 0
    print(f"  {len(df):,} candidate records loaded")

    print("Engineering features ...")
    df_feat = engineer_features(df)

    print("Running detection ...")
    scored = detector.detect(df_feat)
    anomalous = scored[scored["is_anomaly"]]
    print(f"  {len(anomalous):,} anomalies found ({len(anomalous) / len(scored) * 100:.1f}%)")

    if anomalous.empty:
        return 0

    inserted = 0
    with SessionLocal() as db:
        rows = anomalous.to_dict("records")
        for start in range(0, len(rows), batch_size):
            chunk = rows[start:start + batch_size]
            mappings = [
                {
                    "delay_record_id": int(r["delay_record_id"]),
                    "train_id": int(r["train_id"]) if pd.notna(r["train_id"]) else None,
                    "station_id": int(r["station_id"]) if pd.notna(r["station_id"]) else None,
                    "anomaly_date": r["journey_date"],
                    "anomaly_score": float(r["if_score"]),
                    "z_score": float(r["z_score"]),
                    "anomaly_type": r["anomaly_type"],
                    "severity": r["severity"],
                    "explanation": _EXPLANATIONS.get(r["anomaly_type"], "Unusual delay pattern detected."),
                    "is_resolved": False,
                }
                for r in chunk
            ]
            db.bulk_insert_mappings(Anomaly, mappings)
            db.commit()
            inserted += len(mappings)
            print(f"  inserted {inserted:,}/{len(rows):,}")

    logger.info("Anomaly persistence complete", inserted=inserted, days=days)
    print(f"\n✅ {inserted:,} anomaly rows written to the database.")
    return inserted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detect anomalies and persist them to the DB.")
    parser.add_argument("--days", type=int, default=180, help="How far back to scan for un-scored records.")
    parser.add_argument("--limit", type=int, default=300_000, help="Max candidate records to load.")
    parser.add_argument("--batch-size", type=int, default=2_000, help="Insert batch size.")
    args = parser.parse_args()
    run(days=args.days, limit=args.limit, batch_size=args.batch_size)
