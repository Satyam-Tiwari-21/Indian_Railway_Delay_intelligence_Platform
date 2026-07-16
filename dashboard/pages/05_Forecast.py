# dashboard/pages/05_Forecast.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
from dashboard.components.auth_wall import check_auth, show_sidebar_user
from dashboard.components.charts import forecast_chart
from dashboard.utils import api_client as api

st.set_page_config(page_title="Forecast — Railways AI", page_icon="📈", layout="wide")

if not check_auth():
    st.warning("Please log in first.")
    st.stop()

show_sidebar_user()

st.title("📈 Delay Forecast")
st.caption("30-day ahead zone-level delay forecast using trend analysis + Indian seasonality")

ZONES = ["NR", "SR", "CR", "ER", "WR", "NCR", "NER", "ECR", "SCR",
         "SER", "NWR", "WCR", "NFR", "ECOR", "SWR", "SECR"]

ZONE_NAMES = {
    "NR":   "Northern Railway",
    "SR":   "Southern Railway",
    "CR":   "Central Railway",
    "ER":   "Eastern Railway",
    "WR":   "Western Railway",
    "NCR":  "North Central Railway",
    "NER":  "North Eastern Railway",
    "ECR":  "East Central Railway",
    "SCR":  "South Central Railway",
    "SER":  "South Eastern Railway",
    "NWR":  "North Western Railway",
    "WCR":  "West Central Railway",
    "NFR":  "Northeast Frontier Railway",
    "ECOR": "East Coast Railway",
    "SWR":  "South Western Railway",
    "SECR": "South East Central Railway",
}

# ── Controls ───────────────────────────────────────────────────
col_zone, col_days, _ = st.columns([2, 2, 3])
with col_zone:
    selected_zone = st.selectbox(
        "Railway Zone",
        ZONES,
        format_func=lambda z: f"{z} — {ZONE_NAMES.get(z, z)}",
    )
with col_days:
    days = st.slider("Forecast horizon (days)", 7, 90, 30)

st.markdown("---")

# ── Load forecast ──────────────────────────────────────────────
with st.spinner(f"Generating {days}-day forecast for {selected_zone}..."):
    forecast_data = api.get_zone_forecast(selected_zone, days)

if not forecast_data:
    st.warning(
        f"No historical data available for zone **{selected_zone}**. "
        "Load data first: `python data/etl/ingest.py --generate-synthetic --rows 50000`"
    )
    st.stop()

# ── Forecast chart ─────────────────────────────────────────────
st.subheader(f"📊 {days}-Day Forecast — {selected_zone} ({ZONE_NAMES.get(selected_zone, '')})")
st.plotly_chart(forecast_chart(forecast_data, selected_zone), use_container_width=True)

# ── Insight callout ────────────────────────────────────────────
df = pd.DataFrame(forecast_data)
if not df.empty and "predicted_avg_delay" in df.columns:
    max_row = df.loc[df["predicted_avg_delay"].idxmax()]
    min_row = df.loc[df["predicted_avg_delay"].idxmin()]
    avg_val = df["predicted_avg_delay"].mean()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Forecast Avg", f"{avg_val:.1f} min")
    with col2:
        st.metric("📈 Peak Day", f"{max_row['predicted_avg_delay']:.1f} min",
                  delta=str(max_row.get("date", "")), delta_color="inverse")
    with col3:
        st.metric("📉 Best Day", f"{min_row['predicted_avg_delay']:.1f} min",
                  delta=str(min_row.get("date", "")))

st.markdown("---")

# ── Seasonal note ──────────────────────────────────────────────
from datetime import date
current_month = date.today().month
if current_month in [6, 7, 8, 9]:
    st.warning("🌧 **Monsoon Season Active** — Forecasts include monsoon delay multipliers. "
               "Flooding and signal failures typically cause 60–80% higher delays.")
elif current_month in [12, 1]:
    st.warning("🌫 **Fog Season Active** — Northern zones (NR, NCR, NWR) experience "
               "significant visibility-related delays. Dense fog typically adds 45–90 min.")
elif current_month in [10, 11]:
    st.info("🪔 **Festive Season** — Diwali, Dussehra, Chhath Puja cause high passenger "
            "volumes. Expect 20–30% higher delays than normal months.")

# ── Forecast table ─────────────────────────────────────────────
st.subheader("📋 Day-by-Day Forecast")
with st.expander("Show full forecast table"):
    display_df = df.copy()
    col_map = {
        "date": "Date",
        "predicted_avg_delay": "Predicted Avg Delay (min)",
        "lower_80": "Lower 80% CI",
        "upper_80": "Upper 80% CI",
    }
    cols = [c for c in col_map if c in display_df.columns]
    display_df = display_df[cols].rename(columns=col_map)
    if "Predicted Avg Delay (min)" in display_df.columns:
        display_df["Predicted Avg Delay (min)"] = display_df["Predicted Avg Delay (min)"].round(1)

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    csv = display_df.to_csv(index=False)
    st.download_button(
        "⬇️ Download Forecast CSV",
        csv,
        f"forecast_{selected_zone}_{days}days.csv",
        "text/csv",
    )

st.markdown("---")
st.caption(
    "**Methodology:** Linear trend extrapolation from historical zone-level daily avg delay "
    "with Indian seasonality multipliers (monsoon ×1.8, fog ×1.6, festive ×1.2). "
    "In Phase 5 (ML training), this is replaced by a trained Prophet model with Indian holiday calendar."
)