"""
alembic/env.py
───────────────
Alembic migration environment.

Key changes from the default template:
1. Reads DATABASE_URL from app settings (not hardcoded in alembic.ini)
2. Imports Base + all ORM models so autogenerate can detect schema changes
3. Handles the case where models aren't yet implemented (Phase 1)
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool  # type: ignore
from alembic import context

# ── Add project root to Python path ──────────────────────────
# Required so "from app.core..." imports work when alembic runs
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Alembic Config ────────────────────────────────────────────
config = context.config

# Set up Python logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Override sqlalchemy.url from app settings ─────────────────
# This means we NEVER need to touch alembic.ini for the database URL.
# It reads from .env via pydantic-settings.
try:
    from app.core.config import settings
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
except Exception as e:
    # Fallback: read DATABASE_URL directly from environment
    # Useful in CI/CD where pydantic-settings might not be available
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        config.set_main_option("sqlalchemy.url", db_url)
    else:
        raise RuntimeError(
            "DATABASE_URL not found. Set it in .env or as an environment variable."
        ) from e

# ── Import Base and all ORM models ───────────────────────────
# target_metadata enables `alembic revision --autogenerate`
# to detect CREATE/ALTER/DROP TABLE changes automatically.
#
# IMPORTANT: Import EVERY model here, otherwise Alembic won't
# see tables that aren't imported and will try to DROP them.
try:
    from app.core.database import Base  # noqa: F401

    # Phase 2: uncomment as you implement each model
    # from app.models.db.user import User, Role          # noqa: F401
    # from app.models.db.station import Station          # noqa: F401
    # from app.models.db.train import Train              # noqa: F401
    # from app.models.db.route import Route              # noqa: F401
    # from app.models.db.delay_record import DelayRecord # noqa: F401
    # from app.models.db.prediction import Prediction    # noqa: F401
    # from app.models.db.anomaly import Anomaly          # noqa: F401
    # from app.models.db.report import Report            # noqa: F401
    # from app.models.db.audit_log import AuditLog       # noqa: F401

    target_metadata = Base.metadata

except ImportError:
    # Models not implemented yet (Phase 1) — autogenerate will produce empty migrations
    target_metadata = None


# ── Migration Functions ───────────────────────────────────────

def run_migrations_offline() -> None:
    """
    Run migrations without a live DB connection.
    Used in CI or to generate SQL scripts without executing them.
    Run with: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Compare server defaults so Alembic detects DEFAULT value changes
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations with a live DB connection.
    Used in normal development: alembic upgrade head
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # Don't pool connections in migration scripts
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_server_default=True,
            # Include schemas — important for PostgreSQL public schema
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# ── Run ───────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()