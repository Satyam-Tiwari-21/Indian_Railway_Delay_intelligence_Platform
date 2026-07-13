# dashboard/utils/api_client.py
# Wrapper around the FastAPI backend.
# All API calls go through this file — never call requests directly from pages.

import requests
import streamlit as st

BASE_URL = "http://localhost:8000/api/v1"
TIMEOUT  = 15  # seconds


def _headers() -> dict:
    token = st.session_state.get("access_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _handle_401():
    """Clear session and force re-login when token expires."""
    st.session_state.clear()
    st.error("Session expired. Please log in again.")
    st.rerun()


# ── Auth ───────────────────────────────────────────────────────

def login(username: str, password: str) -> dict | None:
    """Returns token dict on success, None on failure."""
    try:
        r = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": username, "password": password},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return r.json()
        return None
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to API. Make sure the server is running at http://localhost:8000")
        return None
    except Exception as e:
        st.error(f"Login error: {e}")
        return None


def get_me() -> dict | None:
    try:
        r = requests.get(f"{BASE_URL}/auth/me", headers=_headers(), timeout=TIMEOUT)
        if r.status_code == 401:
            _handle_401()
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


# ── Analytics ─────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def get_overview(start_date=None, end_date=None) -> dict:
    params = {}
    if start_date: params["start_date"] = str(start_date)
    if end_date:   params["end_date"]   = str(end_date)
    try:
        r = requests.get(f"{BASE_URL}/analytics/overview",
                         headers=_headers(), params=params, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {
        "total_active_trains": 0, "total_stations": 0,
        "avg_delay_minutes": 0.0, "otp_percentage": 0.0,
        "total_records_analysed": 0, "open_anomalies": 0,
        "worst_zone": None, "worst_zone_avg_delay": None,
    }


@st.cache_data(ttl=300, show_spinner=False)
def get_routes(zone=None, category=None, limit=20, sort_by="avg_delay_desc") -> list:
    params = {"limit": limit, "sort_by": sort_by}
    if zone:     params["zone"]     = zone
    if category: params["category"] = category
    try:
        r = requests.get(f"{BASE_URL}/analytics/routes",
                         headers=_headers(), params=params, timeout=TIMEOUT)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def get_zones() -> list:
    try:
        r = requests.get(f"{BASE_URL}/analytics/zones",
                         headers=_headers(), timeout=TIMEOUT)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


@st.cache_data(ttl=600, show_spinner=False)
def get_seasonal(year=None) -> list:
    params = {}
    if year: params["year"] = year
    try:
        r = requests.get(f"{BASE_URL}/analytics/seasonal",
                         headers=_headers(), params=params, timeout=TIMEOUT)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def get_heatmap() -> list:
    try:
        r = requests.get(f"{BASE_URL}/analytics/heatmap",
                         headers=_headers(), timeout=TIMEOUT)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def get_top_delayed(n=10) -> list:
    try:
        r = requests.get(f"{BASE_URL}/analytics/top-delayed",
                         headers=_headers(), params={"n": n}, timeout=TIMEOUT)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


@st.cache_data(ttl=600, show_spinner=False)
def get_categories() -> list:
    try:
        r = requests.get(f"{BASE_URL}/analytics/categories",
                         headers=_headers(), timeout=TIMEOUT)
        return r.json().get("categories", []) if r.status_code == 200 else []
    except Exception:
        return []


@st.cache_data(ttl=600, show_spinner=False)
def get_zones_list() -> list:
    try:
        r = requests.get(f"{BASE_URL}/analytics/zones-list",
                         headers=_headers(), timeout=TIMEOUT)
        return r.json().get("zones", []) if r.status_code == 200 else []
    except Exception:
        return []


# ── Predictions ────────────────────────────────────────────────

def predict_delay(train_number: str, station_code: str, journey_date: str) -> dict | None:
    payload = {
        "train_number":       train_number,
        "query_station_code": station_code,
        "journey_date":       journey_date,
        "include_explanation": True,
    }
    try:
        r = requests.post(f"{BASE_URL}/predictions/delay",
                          headers=_headers(), json=payload, timeout=30)
        if r.status_code == 201:
            return r.json()
        if r.status_code == 404:
            st.error(r.json().get("detail", "Train or station not found"))
        elif r.status_code == 403:
            st.error("Your role does not have permission to make predictions")
        else:
            st.error(f"Prediction failed: {r.json().get('detail', r.text)}")
    except Exception as e:
        st.error(f"Connection error: {e}")
    return None


def get_prediction_history(limit=20) -> list:
    try:
        r = requests.get(f"{BASE_URL}/predictions/history",
                         headers=_headers(), params={"limit": limit}, timeout=TIMEOUT)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


# ── Anomalies ─────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def get_anomaly_feed(severity=None, resolved=False, limit=50) -> dict:
    params = {"resolved": resolved, "limit": limit}
    if severity: params["severity"] = severity
    try:
        r = requests.get(f"{BASE_URL}/anomalies/feed",
                         headers=_headers(), params=params, timeout=TIMEOUT)
        return r.json() if r.status_code == 200 else {"total": 0, "anomalies": [], "critical_count": 0, "high_count": 0, "medium_count": 0}
    except Exception:
        return {"total": 0, "anomalies": [], "critical_count": 0, "high_count": 0, "medium_count": 0}


def resolve_anomaly(anomaly_id: int, note: str) -> bool:
    try:
        r = requests.put(
            f"{BASE_URL}/anomalies/{anomaly_id}/resolve",
            headers=_headers(),
            json={"resolution_note": note},
            timeout=TIMEOUT,
        )
        return r.status_code == 200
    except Exception:
        return False


# ── Forecast ──────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def get_zone_forecast(zone_code: str, days: int = 30) -> list:
    try:
        r = requests.get(
            f"{BASE_URL}/forecast/zone/{zone_code}",
            headers=_headers(), params={"days": days}, timeout=TIMEOUT,
        )
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []