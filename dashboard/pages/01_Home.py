# dashboard/pages/01_Home.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from dashboard.components.auth_wall import check_auth, show_sidebar_user
from dashboard.components.charts import seasonal_chart, zone_bar_chart, otp_donut_chart
from dashboard.utils import api_client as api

st.set_page_config(page_title="Home — Railways AI", page_icon="🏠", layout="wide")

if not check_auth():
    st.warning("Please log in first.")
    st.page_link("dashboard/app.py", label="Go to Login")
    st.stop()

show_sidebar_user()

st.title("🏠 Network Overview")
st.caption("Real-time KPIs across the Indian Railways network")

# ── KPI Cards ──────────────────────────────────────────────────
with st.spinner("Loading network KPIs..."):
    overview = api.get_overview()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="🚂 Active Trains",
        value=f"{overview.get('total_active_trains', 0):,}",
    )
with col2:
    avg_delay = overview.get("avg_delay_minutes", 0)
    st.metric(
        label="⏱ Avg Delay",
        value=f"{avg_delay:.1f} min",
        delta=f"Network average",
        delta_color="off",
    )
with col3:
    otp = overview.get("otp_percentage", 0)
    st.metric(
        label="✅ On-Time Performance",
        value=f"{otp:.1f}%",
        delta="Trains arriving ≤5 min late",
        delta_color="off",
    )
with col4:
    anomalies = overview.get("open_anomalies", 0)
    st.metric(
        label="🚨 Open Anomalies",
        value=f"{anomalies}",
        delta="Unresolved alerts",
        delta_color="inverse" if anomalies > 0 else "off",
    )

st.markdown("---")

# ── Charts Row ─────────────────────────────────────────────────
col_left, col_right = st.columns([3, 2])

with col_left:
    st.subheader("📅 Monthly Delay Pattern")
    with st.spinner("Loading seasonal data..."):
        seasonal = api.get_seasonal()
    if seasonal:
        st.plotly_chart(seasonal_chart(seasonal), use_container_width=True)
    else:
        st.info("No seasonal data yet. Load data first: `python data/etl/ingest.py --generate-synthetic`")

with col_right:
    st.subheader("🎯 OTP Breakdown")
    otp_val = overview.get("otp_percentage", 0)
    st.plotly_chart(otp_donut_chart(otp_val), use_container_width=True)

    worst_zone = overview.get("worst_zone")
    if worst_zone:
        worst_delay = overview.get("worst_zone_avg_delay", 0)
        st.error(f"⚠️ **Worst Zone:** {worst_zone} — Avg {worst_delay:.1f} min delay")

st.markdown("---")

# ── Zone Comparison ────────────────────────────────────────────
st.subheader("🗺️ Zone-wise Delay Comparison")
with st.spinner("Loading zone data..."):
    zones = api.get_zones()

if zones:
    st.plotly_chart(zone_bar_chart(zones), use_container_width=True)
else:
    st.info("No zone data available yet.")

st.markdown("---")

# ── Top Delayed Routes ─────────────────────────────────────────
st.subheader("🚂 Top 10 Most Delayed Routes")
with st.spinner("Loading route data..."):
    top_routes = api.get_top_delayed(n=10)

if top_routes:
    import pandas as pd
    df = pd.DataFrame(top_routes)
    display_cols = {
        "rank": "Rank",
        "train_number": "Train No.",
        "train_name": "Train Name",
        "origin_code": "Origin",
        "destination_code": "Destination",
        "avg_delay_minutes": "Avg Delay (min)",
        "otp_percentage": "OTP %",
    }
    cols_available = [c for c in display_cols if c in df.columns]
    df_display = df[cols_available].rename(columns=display_cols)
    st.dataframe(df_display, use_container_width=True, hide_index=True)
else:
    st.info("No route data available yet.")

# ── Footer ─────────────────────────────────────────────────────
st.markdown("---")
records = overview.get("total_records_analysed", 0)
st.caption(f"📊 Based on {records:,} delay records analysed | India Railways Delay Intelligence Platform")