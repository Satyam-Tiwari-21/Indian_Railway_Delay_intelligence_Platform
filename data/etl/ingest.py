# data/etl/ingest.py
# Full ETL pipeline: raw CSV files → PostgreSQL tables.
#
# Run: python data/etl/ingest.py --source data/raw/delay_records.csv
# Or:  python data/etl/ingest.py --generate-synthetic --rows 50000
#
# The --generate-synthetic flag creates realistic fake data so you can
# test the full stack without waiting for a real dataset download.

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.database import SessionLocal, check_db_connection
from app.core.logging_config import setup_logging, get_logger
from data.etl.clean import clean_delay_records, clean_stations

logger = get_logger(__name__)

BATCH_SIZE = 5_000   # Rows per DB insert batch


# ── Synthetic data generator ───────────────────────────────────
# Generates realistic Indian Railways delay data for testing.

def generate_synthetic_data(n_rows: int = 50_000) -> pd.DataFrame:
    """
    Create synthetic delay records matching Indian Railways patterns:
    - Monsoon months (Jun–Sep) have higher delays
    - Passenger trains have higher delays than Rajdhani
    - Northern zone has fog delays in Dec–Jan
    - Delay compounds along the route
    """
    print(f"\nGenerating {n_rows:,} synthetic delay records...")
    np.random.seed(42)

    # ── Reference data ─────────────────────────────────────────
    stations = [
        ("NDLS", "New Delhi",          "NR",  28.6419, 77.2194),
        ("HWH",  "Howrah Junction",    "ER",  22.5839, 88.3422),
        ("MAS",  "Chennai Central",    "SR",  13.0827, 80.2707),
        ("BCT",  "Mumbai Central",     "WR",  18.9712, 72.8194),
        ("SBC",  "Bengaluru City",     "SWR", 12.9766, 77.5659),
        ("ALD",  "Prayagraj Junction", "NCR", 25.4358, 81.8463),
        ("BSB",  "Varanasi Junction",  "NER", 25.3176, 82.9739),
        ("CNB",  "Kanpur Central",     "NCR", 26.4499, 80.3319),
        ("LKO",  "Lucknow NR",         "NR",  26.8467, 80.9462),
        ("JPU",  "Jaipur Junction",    "NWR", 26.9124, 75.7873),
        ("ASR",  "Amritsar Junction",  "NR",  31.6340, 74.8723),
        ("GHY",  "Guwahati",           "NFR", 26.1445, 91.7362),
        ("BBS",  "Bhubaneswar",        "ECoR",20.2961, 85.8245),
        ("HYB",  "Hyderabad Deccan",   "SCR", 17.3753, 78.4744),
        ("ADI",  "Ahmedabad Junction", "WR",  23.0258, 72.5978),
        ("PUNE", "Pune Junction",      "CR",  18.5286, 73.8742),
        ("NGP",  "Nagpur Junction",    "CR",  21.1458, 79.0882),
        ("BPL",  "Bhopal Junction",    "WCR", 23.2599, 77.4126),
        ("GWL",  "Gwalior Junction",   "NCR", 26.2109, 78.1765),
        ("PNBE", "Patna Junction",     "ECR", 25.5941, 85.1376),
    ]

    trains = [
        ("12301", "Howrah Rajdhani",        "Rajdhani",  "NR",  "HWH",  "NDLS", 1441, 22),
        ("12302", "New Delhi Rajdhani",      "Rajdhani",  "NR",  "NDLS", "HWH",  1441, 22),
        ("12951", "Mumbai Rajdhani",         "Rajdhani",  "WR",  "BCT",  "NDLS", 1385, 16),
        ("12001", "New Delhi Shatabdi",      "Shatabdi",  "NR",  "NDLS", "BSB",  826,  15),
        ("12259", "Sealdah Duronto",         "Duronto",   "ER",  "SDAH", "NDLS", 1453, 0),
        ("12621", "Tamil Nadu Express",      "Superfast", "SR",  "MAS",  "NDLS", 2175, 32),
        ("12621", "TN Express",              "Superfast", "SR",  "MAS",  "NDLS", 2175, 32),
        ("11014", "Coimbatore Express",      "Express",   "CR",  "LTT",  "CBE",  1152, 24),
        ("19019", "Saurashtra Mail",         "Mail",      "WR",  "BCT",  "ADI",  492,  12),
        ("54003", "Delhi Ambala Passenger",  "Passenger", "NR",  "NDLS", "UMB",  363,  28),
        ("54011", "Delhi Saharanpur Pass",   "Passenger", "NR",  "NDLS", "SRE",  176,  14),
        ("12723", "Telangana Express",       "Superfast", "SCR", "HYB",  "NDLS", 1661, 27),
        ("16503", "Kannur Express",          "Express",   "SR",  "SBC",  "CAN",  647,  18),
        ("12875", "Neelachal Express",       "Express",   "SER", "HWH",  "PURI", 500,  12),
        ("22691", "Rajdhani Express",        "Rajdhani",  "SWR", "SBC",  "NDLS", 2367, 23),
    ]

    station_codes = [s[0] for s in stations]
    categories    = ["Rajdhani", "Shatabdi", "Superfast", "Express", "Mail", "Passenger"]

    # ── Generate records ───────────────────────────────────────
    dates = pd.date_range(
        start="2022-01-01", end="2024-12-31", freq="D"
    )

    records = []
    for _ in range(n_rows):
        journey_date = pd.Timestamp(np.random.choice(dates))
        month = journey_date.month
        dow   = journey_date.dayofweek
        train = trains[np.random.randint(len(trains))]
        station_idx = np.random.randint(len(stations))
        station = stations[station_idx]

        # Base delay depends on category
        category = train[2]
        base_delays = {
            "Rajdhani": 8, "Shatabdi": 7, "Duronto": 10,
            "Superfast": 18, "Mail": 22, "Express": 25, "Passenger": 45,
        }
        base = base_delays.get(category, 20)

        # Seasonal adjustments
        if month in (6, 7, 8, 9):   base *= np.random.uniform(1.5, 2.2)  # Monsoon
        if month in (12, 1):         base *= np.random.uniform(1.3, 1.9)  # Fog
        if month in (10, 11):        base *= np.random.uniform(1.1, 1.3)  # Festive

        # Zone adjustment — Northern zone has more fog delays
        if station[2] == "NR" and month in (12, 1):
            base *= np.random.uniform(1.2, 1.6)

        # Add noise
        delay = max(-15, int(np.random.normal(base, base * 0.4)))

        reason_code = None
        if delay > 60:
            if month in (6, 7, 8, 9):   reason_code = "FLOOD"
            elif month in (12, 1):       reason_code = "FOG"
            elif np.random.random() < 0.3: reason_code = "SIGNAL_FAIL"
            else:                          reason_code = "LATE_RUNNING"

        records.append({
            "train_number":            train[0],
            "train_name":              train[1],
            "category":                category,
            "zone":                    train[3],
            "origin_code":             train[4],
            "destination_code":        train[5],
            "station_code":            station[0],
            "station_name":            station[1],
            "journey_date":            journey_date.date(),
            "arrival_delay_minutes":   delay,
            "departure_delay_minutes": max(0, delay - np.random.randint(0, 5)),
            "reason_code":             reason_code,
            "weather_condition":       "HEAVY_RAIN" if month in (7, 8) else "FOG" if month in (12, 1) else "CLEAR",
            "data_source":             "synthetic",
            "is_cancelled":            np.random.random() < 0.002,
        })

    df = pd.DataFrame(records)
    print(f"  Generated {len(df):,} records spanning 2022–2024")
    return df


# ── Station upsert ─────────────────────────────────────────────

def upsert_stations(db: Session, stations_data: list[dict]) -> int:
    """Insert stations, skipping any that already exist."""
    from app.models.db.station import Station
    count = 0
    for row in stations_data:
        existing = db.query(Station).filter(
            Station.station_code == row["station_code"]
        ).first()
        if existing is None:
            db.add(Station(**row))
            count += 1
    db.flush()
    return count


# ── Train upsert ───────────────────────────────────────────────

def upsert_trains(
    db: Session,
    df: pd.DataFrame,
    station_code_to_id: dict[str, int],
) -> dict[str, int]:
    """
    Insert trains from DataFrame, return {train_number: train_id}.
    Skips trains that already exist.
    """
    from app.models.db.train import Train

    train_map: dict[str, int] = {}
    seen = set()

    for _, row in df.iterrows():
        tn = str(row.get("train_number", "")).strip()
        if not tn or tn in seen:
            continue
        seen.add(tn)

        existing = db.query(Train).filter(Train.train_number == tn).first()
        if existing:
            train_map[tn] = existing.id
            continue

        origin = row.get("origin_code") or row.get("station_code", "NDLS")
        dest   = row.get("destination_code", "NDLS")
        origin_id = station_code_to_id.get(origin)
        dest_id   = station_code_to_id.get(dest)

        if not origin_id or not dest_id:
            continue  # Skip if stations not loaded yet

        t = Train(
            train_number=tn,
            name=str(row.get("train_name", f"Train {tn}")),
            category=str(row.get("category", "Express")),
            zone=row.get("zone"),
            origin_station_id=origin_id,
            destination_station_id=dest_id,
            is_active=True,
        )
        db.add(t)
        db.flush()
        train_map[tn] = t.id

    return train_map


# ── Delay record bulk insert ───────────────────────────────────

def insert_delay_records(
    db: Session,
    df: pd.DataFrame,
    train_map: dict[str, int],
    station_map: dict[str, int],
) -> int:
    """Bulk-insert delay records in batches of BATCH_SIZE."""
    from app.models.db.delay_record import DelayRecord

    records = []
    skipped = 0

    for _, row in df.iterrows():
        tn  = str(row.get("train_number", "")).strip()
        sc  = str(row.get("station_code", "")).strip().upper()
        tid = train_map.get(tn)
        sid = station_map.get(sc)

        if not tid or not sid:
            skipped += 1
            continue

        records.append({
            "train_id":                tid,
            "station_id":              sid,
            "journey_date":            row.get("journey_date"),
            "arrival_delay_minutes":   row.get("arrival_delay_minutes"),
            "departure_delay_minutes": row.get("departure_delay_minutes"),
            "reason_code":             row.get("reason_code"),
            "weather_condition":       row.get("weather_condition"),
            "data_source":             row.get("data_source", "historical"),
            "is_cancelled":            bool(row.get("is_cancelled", False)),
        })

    if skipped:
        print(f"  Skipped {skipped:,} rows (train/station not in DB)")

    # Bulk insert in batches
    total = 0
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        db.bulk_insert_mappings(DelayRecord, batch)
        db.flush()
        total += len(batch)
        print(f"  Inserted batch {i // BATCH_SIZE + 1}: {total:,}/{len(records):,}")

    return total


# ── Main pipeline ─────────────────────────────────────────────

def run_ingestion(
    csv_path: Path | None = None,
    synthetic: bool = False,
    n_synthetic: int = 50_000,
):
    """
    Full ETL pipeline:
    1. Load raw CSV (or generate synthetic data)
    2. Clean the data
    3. Upsert stations
    4. Upsert trains
    5. Bulk insert delay records
    """
    setup_logging()

    # ── DB health check ────────────────────────────────────────
    status = check_db_connection()
    if status["status"] != "healthy":
        print("❌ Cannot connect to PostgreSQL. Run: docker-compose up -d postgres")
        sys.exit(1)

    # ── Load source data ───────────────────────────────────────
    if synthetic:
        df = generate_synthetic_data(n_synthetic)
    elif csv_path:
        print(f"\nLoading {csv_path}...")
        try:
            df = pd.read_csv(csv_path, encoding="utf-8", low_memory=False)
        except UnicodeDecodeError:
            df = pd.read_csv(csv_path, encoding="latin-1", low_memory=False)
        print(f"  Loaded {len(df):,} raw rows")
        df = clean_delay_records(df)
    else:
        print("❌ Provide --source <path> or --generate-synthetic")
        sys.exit(1)

    t0 = time.time()

    with SessionLocal() as db:
        # ── 1. Load stations first ─────────────────────────────
        print("\n[1/3] Loading stations...")

        # Static reference stations (always loaded)
        BASE_STATIONS = [
            {"station_code": "NDLS", "name": "New Delhi",          "zone": "NR",   "latitude": 28.6419, "longitude": 77.2194, "is_junction": True},
            {"station_code": "HWH",  "name": "Howrah Junction",    "zone": "ER",   "latitude": 22.5839, "longitude": 88.3422, "is_junction": True},
            {"station_code": "MAS",  "name": "Chennai Central",    "zone": "SR",   "latitude": 13.0827, "longitude": 80.2707, "is_junction": True},
            {"station_code": "BCT",  "name": "Mumbai Central",     "zone": "WR",   "latitude": 18.9712, "longitude": 72.8194, "is_junction": True},
            {"station_code": "SBC",  "name": "Bengaluru City",     "zone": "SWR",  "latitude": 12.9766, "longitude": 77.5659, "is_junction": True},
            {"station_code": "ALD",  "name": "Prayagraj Junction", "zone": "NCR",  "latitude": 25.4358, "longitude": 81.8463, "is_junction": True},
            {"station_code": "BSB",  "name": "Varanasi Junction",  "zone": "NER",  "latitude": 25.3176, "longitude": 82.9739, "is_junction": True},
            {"station_code": "CNB",  "name": "Kanpur Central",     "zone": "NCR",  "latitude": 26.4499, "longitude": 80.3319, "is_junction": True},
            {"station_code": "LKO",  "name": "Lucknow NR",         "zone": "NR",   "latitude": 26.8467, "longitude": 80.9462, "is_junction": True},
            {"station_code": "JPU",  "name": "Jaipur Junction",    "zone": "NWR",  "latitude": 26.9124, "longitude": 75.7873, "is_junction": True},
            {"station_code": "ASR",  "name": "Amritsar Junction",  "zone": "NR",   "latitude": 31.6340, "longitude": 74.8723, "is_junction": False},
            {"station_code": "GHY",  "name": "Guwahati",           "zone": "NFR",  "latitude": 26.1445, "longitude": 91.7362, "is_junction": True},
            {"station_code": "HYB",  "name": "Hyderabad Deccan",   "zone": "SCR",  "latitude": 17.3753, "longitude": 78.4744, "is_junction": True},
            {"station_code": "ADI",  "name": "Ahmedabad Junction", "zone": "WR",   "latitude": 23.0258, "longitude": 72.5978, "is_junction": True},
            {"station_code": "PUNE", "name": "Pune Junction",      "zone": "CR",   "latitude": 18.5286, "longitude": 73.8742, "is_junction": True},
            {"station_code": "NGP",  "name": "Nagpur Junction",    "zone": "CR",   "latitude": 21.1458, "longitude": 79.0882, "is_junction": True},
            {"station_code": "BPL",  "name": "Bhopal Junction",    "zone": "WCR",  "latitude": 23.2599, "longitude": 77.4126, "is_junction": False},
            {"station_code": "PNBE", "name": "Patna Junction",     "zone": "ECR",  "latitude": 25.5941, "longitude": 85.1376, "is_junction": True},
            {"station_code": "SDAH", "name": "Sealdah",            "zone": "ER",   "latitude": 22.5649, "longitude": 88.3706, "is_junction": False},
            {"station_code": "UMB",  "name": "Ambala Cantonment",  "zone": "NR",   "latitude": 30.3782, "longitude": 76.8285, "is_junction": True},
        ]

        # Add any stations from CSV not in base list
        if "station_code" in df.columns:
            csv_stations = df[["station_code", "station_name", "zone"]].drop_duplicates("station_code")
            existing_codes = {s["station_code"] for s in BASE_STATIONS}
            for _, row in csv_stations.iterrows():
                if row["station_code"] not in existing_codes:
                    BASE_STATIONS.append({
                        "station_code": row["station_code"],
                        "name": str(row.get("station_name") or row["station_code"]),
                        "zone": row.get("zone"),
                        "is_junction": False,
                    })

        added = upsert_stations(db, BASE_STATIONS)
        print(f"  ✅  {added} new stations added ({len(BASE_STATIONS)} total in reference)")

        # Build station code → id map
        from app.models.db.station import Station
        station_map = {
            s.station_code: s.id
            for s in db.query(Station).all()
        }

        # ── 2. Load trains ─────────────────────────────────────
        print("\n[2/3] Loading trains...")
        train_map = upsert_trains(db, df, station_map)
        print(f"  ✅  {len(train_map)} trains in DB")

        # ── 3. Insert delay records ────────────────────────────
        print("\n[3/3] Inserting delay records...")
        inserted = insert_delay_records(db, df, train_map, station_map)

        db.commit()

    elapsed = time.time() - t0
    print(f"\n✅  Ingestion complete!")
    print(f"   Records inserted: {inserted:,}")
    print(f"   Time taken:       {elapsed:.1f}s")
    print(f"   Rate:             {inserted / elapsed:.0f} rows/sec")
    print(f"\nNext: open http://localhost:8000/api/v1/analytics/overview to see your data.")


# ── CLI ────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Indian Railways delay data ingestion")
    parser.add_argument("--source",             type=Path, help="Path to source CSV file")
    parser.add_argument("--generate-synthetic", action="store_true", help="Generate synthetic data instead of loading CSV")
    parser.add_argument("--rows",               type=int,  default=50_000, help="Number of synthetic rows (default 50000)")
    args = parser.parse_args()

    run_ingestion(
        csv_path=args.source,
        synthetic=args.generate_synthetic,
        n_synthetic=args.rows,
    )