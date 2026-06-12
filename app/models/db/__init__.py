# app/models/db/__init__.py
# Import every ORM model here.
# This ensures Alembic's autogenerate sees ALL tables
# when you run: alembic revision --autogenerate

from app.models.db.user import Role, User
from app.models.db.station import Station
from app.models.db.train import Train
from app.models.db.route import Route
from app.models.db.delay_record import DelayRecord
from app.models.db.prediction import Prediction
from app.models.db.anomaly import Anomaly
from app.models.db.report import Report
from app.models.db.audit_log import AuditLog

__all__ = [
    "Role",
    "User",
    "Station",
    "Train",
    "Route",
    "DelayRecord",
    "Prediction",
    "Anomaly",
    "Report",
    "AuditLog",
]