"""
app/core/logging_config.py
───────────────────────────
Structured logging setup using structlog + stdlib logging.

IMPORTANT: Named logging_config.py, NOT logging.py.
           logging.py would shadow Python's built-in logging module,
           causing ImportError across the entire project.

Features:
  - Console output: colored in development, JSON in production
  - Rotating file logs: app.log (all), error.log (ERROR+), access.log (requests)
  - Request ID injection: every log line includes the request_id for tracing
  - Automatic correlation: log statements in the same request share an ID

Usage:
    from app.core.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("Train delay recorded", train_id=12301, delay_minutes=45)
"""

import logging
import logging.handlers
import sys
import uuid
from pathlib import Path
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.core.config import settings


# ── Request ID ────────────────────────────────────────────────────────────────

def get_request_id() -> str:
    """Generate a unique ID for request tracing."""
    return str(uuid.uuid4())[:8]  # Short 8-char ID is readable in logs


# ── Stdlib Logging Setup ──────────────────────────────────────────────────────

def _configure_stdlib_logging() -> None:
    """
    Configure Python's standard library logging.
    structlog will forward to stdlib, so we configure handlers here.
    """
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level = getattr(logging, settings.LOG_LEVEL, logging.INFO)

    # Root logger — captures everything
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any handlers added by uvicorn or previous calls
    root_logger.handlers.clear()

    # ── Formatter ─────────────────────────────────────────────────────────────
    # Plain format for file logs (structlog handles console formatting separately)
    file_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Console Handler ───────────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    # structlog handles console formatting — keep this formatter minimal
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(console_handler)

    # ── App Log: All levels, rotating at 10MB, keep 5 backups ─────────────────
    app_log_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    app_log_handler.setLevel(log_level)
    app_log_handler.setFormatter(file_formatter)
    root_logger.addHandler(app_log_handler)

    # ── Error Log: ERROR and above only ───────────────────────────────────────
    error_log_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "error.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=10,  # Keep more error backups
        encoding="utf-8",
    )
    error_log_handler.setLevel(logging.ERROR)
    error_log_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_log_handler)

    # ── Silence noisy third-party loggers ─────────────────────────────────────
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if settings.DB_ECHO else logging.WARNING
    )
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)   # We log requests ourselves
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("alembic").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("prophet").setLevel(logging.WARNING)
    logging.getLogger("mlflow").setLevel(logging.WARNING)


# ── Structlog Configuration ───────────────────────────────────────────────────

def _configure_structlog() -> None:
    """
    Configure structlog for structured, context-aware logging.

    Development: colored, human-readable console output
    Production:  JSON output — parseable by log aggregators (Datadog, ELK, CloudWatch)
    """
    shared_processors = [
        # Merge any context variables bound with bind_contextvars() (request_id etc.)
        structlog.contextvars.merge_contextvars,
        # Add log level as a string field
        structlog.stdlib.add_log_level,
        # Add logger name
        structlog.stdlib.add_logger_name,
        # ISO 8601 timestamp
        structlog.processors.TimeStamper(fmt="iso"),
        # Format positional args: logger.info("msg %s", value) → "msg value"
        structlog.stdlib.PositionalArgumentsFormatter(),
        # Format stack traces for exception logging
        structlog.processors.StackInfoRenderer(),
        # Format exception info
        structlog.processors.format_exc_info,
    ]

    if settings.is_development:
        # Colored, human-readable output for local development
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        )
    else:
        # JSON output for production — machine-parseable
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


# ── Public Interface ──────────────────────────────────────────────────────────

def setup_logging() -> None:
    """
    Initialize the entire logging system.
    Call this ONCE at application startup in app/main.py lifespan.
    """
    _configure_stdlib_logging()
    _configure_structlog()

    logger = get_logger(__name__)
    logger.info(
        "Logging initialized",
        environment=settings.ENVIRONMENT,
        log_level=settings.LOG_LEVEL,
        log_dir=settings.LOG_DIR,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a named logger. Use __name__ for automatic module-level naming.

    Example:
        logger = get_logger(__name__)
        logger.info("User logged in", user_id="abc", role="analyst")
        logger.warning("Slow query", duration_ms=1500, query="SELECT...")
        logger.error("DB connection failed", exc_info=True)
    """
    return structlog.get_logger(name)


# ── FastAPI Middleware Helper ──────────────────────────────────────────────────

def bind_request_context(request_id: str | None = None, **kwargs: Any) -> str:
    """
    Bind request-scoped context variables so all log lines within a request
    automatically include the request_id (and any other kwargs).

    Called in the request logging middleware (app/api/middleware.py).

    Returns the request_id for inclusion in response headers.
    """
    rid = request_id or get_request_id()
    clear_contextvars()  # Clear previous request's context
    bind_contextvars(request_id=rid, **kwargs)
    return rid


def clear_request_context() -> None:
    """Clear context variables at end of request. Called in middleware cleanup."""
    clear_contextvars()