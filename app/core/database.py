"""
app/core/database.py
─────────────────────
SQLAlchemy engine, session factory, and declarative base.

Architecture:
  - Synchronous SQLAlchemy (simpler, sufficient for this project's load)
  - Connection pooling via QueuePool (default for PostgreSQL)
  - pool_pre_ping=True: validates connections before use (handles stale connections)
  - Session is provided as a FastAPI dependency via get_db()

All ORM models in app/models/db/ import Base from this file.
All API routes get a DB session via Depends(get_db).

Usage (in a service):
    from app.core.database import get_db
    # FastAPI injects db automatically when used as Depends(get_db)

Usage (in a script/CLI):
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        result = db.execute(text("SELECT 1"))
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# ── Engine ────────────────────────────────────────────────────────────────────

engine = create_engine(
    settings.DATABASE_URL,
    # Connection pool settings (read from config.py / .env)
    pool_size=settings.DB_POOL_SIZE,           # Persistent connections kept open
    max_overflow=settings.DB_MAX_OVERFLOW,     # Extra connections allowed under burst load
    pool_timeout=settings.DB_POOL_TIMEOUT,     # Seconds to wait for a connection from pool
    pool_recycle=settings.DB_POOL_RECYCLE,     # Recycle connections older than this (prevent stale)
    # pool_pre_ping: runs "SELECT 1" before giving out a connection
    # Prevents "server closed the connection unexpectedly" errors after DB restart
    pool_pre_ping=True,
    # SQL query logging — only in development and only if DB_ECHO=true
    echo=settings.DB_ECHO,
    # Connection-level settings passed to psycopg2
    connect_args={
        "connect_timeout": 10,                 # Fail fast if DB unreachable (seconds)
        "application_name": "railways_api",    # Shows in pg_stat_activity for debugging
    },
)


# ── Session Factory ───────────────────────────────────────────────────────────

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,   # Never auto-commit — we control transactions explicitly
    autoflush=False,    # Don't auto-flush before queries — we control this
    expire_on_commit=True,  # ORM objects expire after commit (re-fetched on next access)
)


# ── Declarative Base ──────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    All models in app/models/db/ inherit from this:
        from app.core.database import Base
        class Train(Base):
            __tablename__ = "trains"
            ...

    Alembic uses Base.metadata to detect schema changes and generate migrations.
    """
    pass


# ── FastAPI Dependency ─────────────────────────────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session per request.

    - Opens a session at the start of the request
    - Rolls back on any unhandled exception (prevents partial writes)
    - Always closes the session (returns connection to pool)

    Usage in a route:
        @router.get("/trains")
        def list_trains(db: Session = Depends(get_db)):
            return db.query(Train).all()

    Usage in a service (passed from route):
        class TrainRepository:
            def __init__(self, db: Session): self.db = db
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()       # Auto-commit if no exception was raised
    except Exception:
        db.rollback()     # Roll back any partial changes on error
        raise
    finally:
        db.close()        # Always return connection to pool


# ── Context Manager (for scripts/CLI, not FastAPI) ────────────────────────────

@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager version of get_db() for use outside of FastAPI.
    Use in CLI scripts, data ingestion pipeline, ML training.

    Example:
        from app.core.database import get_db_context
        with get_db_context() as db:
            trains = db.query(Train).filter(Train.is_active == True).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── Health Check ──────────────────────────────────────────────────────────────

def check_db_connection() -> dict:
    """
    Verifies the database is reachable and returns diagnostic info.
    Called by GET /health and at startup.

    Returns:
        {"status": "healthy", "pool_size": 5, "checked_out": 0}
        {"status": "unhealthy", "error": "connection refused"}
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        pool = engine.pool
        return {
            "status": "healthy",
            "pool_size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.checkedin(),
        }
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
        }


# ── Connection Event Hooks ─────────────────────────────────────────────────────

@event.listens_for(engine, "connect")
def set_search_path(dbapi_connection, connection_record):
    """
    Set PostgreSQL search_path on every new connection.
    Ensures queries find tables in the public schema by default.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("SET search_path TO public")
    cursor.close()


@event.listens_for(engine, "checkout")
def log_pool_checkout(dbapi_connection, connection_record, connection_proxy):
    """Log when connection pool is under pressure (for monitoring)."""
    pool = engine.pool
    if pool.checkedout() >= pool.size():
        logger.warning(
            "Connection pool at capacity",
            checked_out=pool.checkedout(),
            pool_size=pool.size(),
            overflow=pool.overflow(),
        )