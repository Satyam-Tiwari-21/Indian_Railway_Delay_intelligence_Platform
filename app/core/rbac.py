# app/core/rbac.py
# Role constants and permission registry.
# The actual FastAPI dependency (require_permission) lives in app/api/deps.py
# to avoid circular imports (core should not depend on api).

# Role hierarchy — higher number = more access
ROLE_HIERARCHY: dict[str, int] = {
    "viewer":  1,
    "officer": 2,
    "analyst": 3,
    "admin":   4,
}

# All valid permission keys — must match keys in the roles.permissions JSONB column
PERMISSIONS: dict[str, str] = {
    "can_predict": "Make delay predictions via the Prediction API",
    "can_export":  "Export data as CSV or generate PDF reports",
    "can_admin":   "Manage users, roles, and system settings",
    "can_retrain": "Trigger ML model retraining pipeline",
}

# Default permission sets per role — used when seeding the roles table
ROLE_PERMISSIONS: dict[str, dict[str, bool]] = {
    "admin": {
        "can_predict": True,
        "can_export":  True,
        "can_admin":   True,
        "can_retrain": True,
    },
    "analyst": {
        "can_predict": True,
        "can_export":  True,
        "can_admin":   False,
        "can_retrain": False,
    },
    "officer": {
        "can_predict": True,
        "can_export":  False,
        "can_admin":   False,
        "can_retrain": False,
    },
    "viewer": {
        "can_predict": False,
        "can_export":  False,
        "can_admin":   False,
        "can_retrain": False,
    },
}
