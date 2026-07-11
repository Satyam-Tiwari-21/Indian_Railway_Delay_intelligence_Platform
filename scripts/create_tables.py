"""
scripts/create_tables.py
Creates all database tables directly from SQLAlchemy models.
Use this instead of alembic when migration is failing.

Run: python scripts/create_tables.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.core.database import engine, check_db_connection
from app.core.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def create_all_tables():
    print("\nChecking database connection...")
    status = check_db_connection()
    if status["status"] != "healthy":
        print(f"❌ Cannot connect to database: {status.get('error')}")
        print("   Check your DATABASE_URL in .env file")
        sys.exit(1)
    print("  ✅ Database connected\n")

    print("Importing all models...")
    # Import every model so SQLAlchemy knows about them
    from app.core.database import Base

    # Import all models — this registers them with Base.metadata
    from app.models.db.user import User, Role
    from app.models.db.station import Station
    from app.models.db.train import Train
    from app.models.db.route import Route
    from app.models.db.delay_record import DelayRecord
    from app.models.db.prediction import Prediction
    from app.models.db.anomaly import Anomaly
    from app.models.db.report import Report
    from app.models.db.audit_log import AuditLog

    print(f"  Found {len(Base.metadata.tables)} tables to create:")
    for table_name in sorted(Base.metadata.tables.keys()):
        print(f"    - {table_name}")

    print("\nCreating tables...")
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        # checkfirst=True means: skip tables that already exist
        print("\n✅ All tables created successfully!")
        print("\nNext step: python scripts/seed.py")
    except Exception as e:
        print(f"\n❌ Failed to create tables: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    create_all_tables()