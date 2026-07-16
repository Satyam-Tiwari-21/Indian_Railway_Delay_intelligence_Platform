# dashboard/pages/02_Analytics.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
from dashboard.components.auth_wall import check_auth, show_sidebar_user
from dashboard.components.charts import route_bar_chart, seasonal_chart, zone_bar_chart
from dashboard.components.maps import station_heatmap
from dashboard.utils import api_client as api

st.set_page_config(page_title="Analytics — Railways AI", page_icon="📊", layout="wide")

if not check_auth():
    st.warning("Please log in first.")
    st.stop()

show_sidebar_user()

st.title("📊 Analytics Dashboard")
st.caption("Deep-dive route, zone and seasonal analysis")

# ── Sidebar Filters ────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 Filters")
    zones_list     = ["All"] + (api.get_zones_list() or [])
    categories     = ["All"] + (api.get_categories() or [])
    selected_zone  = st.selectbox("Railway Zone", zones_list)
    selected_cat   = st.selectbox("Train Category", categories)
    top_n          = st.slider("Top N Routes", 5, 50, 20)
    sort_by        = st.radio("Sort routes by", ["Most Delayed", "Most Punctual"])

zone_param = None if selected_zone == "All" else selected_zone
cat_param  = None if selected_cat  == "All" else selected_cat
sort_param = "avg_delay_desc" if sort_by == "Most Delayed" else "otp_asc"

# ── Route Analysis ─────────────────────────────────────────────
st.subheader("🚂 Route Delay Analysis")
with st.spinner("Loading route data..."):
    routes = api.get_routes(zone=zone_param, category=cat_param,
                            limit=top_n, sort_by=sort_param)

tab1, tab2 = st.tabs(["📊 Chart", "📋 Table"])

with tab1:
    if routes:
        st.plotly_chart(route_bar_chart(routes, top_n=top_n), use_container_width=True)
    else:
        st.info("No route data available. Load data first.")

with tab2:
    if routes:
        df = pd.DataFrame(routes)
        col_map = {
            "train_number": "Train No.",
            "train_name": "Name",
            "category": "Category",
            "zone": "Zone",
            "origin_code": "From",
            "destination_code": "To",
            "avg_delay_minutes": "Avg Delay (min)",
            "otp_percentage": "OTP %",
            "total_runs": "Total Runs",
            "severe_delay_count": "Severe Delays",
        }
        cols = [c for c in col_map if c in df.columns]
        st.dataframe(
            df[cols].rename(columns=col_map),
            use_container_width=True,
            hide_index=True,
        )
        # Download button
        csv = df[cols].rename(columns=col_map).to_csv(index=False)
        st.download_button("⬇️ Download CSV", csv, "route_analysis.csv", "text/csv")
    else:
        st.info("No data available.")

st.markdown("---")

# ── Seasonal Pattern ───────────────────────────────────────────
st.subheader("📅 Seasonal Delay Pattern")
with st.spinner("Loading seasonal data..."):
    seasonal = api.get_seasonal()

if seasonal:
    st.plotly_chart(seasonal_chart(seasonal), use_container_width=True)

    # Insight callout
    df_s = pd.DataFrame(seasonal)
    if not df_s.empty and "avg_delay_minutes" in df_s.columns:
        monsoon_avg = df_s[df_s["is_monsoon"] == True]["avg_delay_minutes"].mean() if "is_monsoon" in df_s.columns else 0
        normal_avg  = df_s[df_s["is_monsoon"] == False]["avg_delay_minutes"].mean() if "is_monsoon" in df_s.columns else 0
        if monsoon_avg > 0 and normal_avg > 0:
            st.info(f"🌧 **Monsoon Impact:** Avg delay is **{monsoon_avg:.1f} min** during monsoon vs **{normal_avg:.1f} min** in other months — a **{((monsoon_avg/normal_avg)-1)*100:.0f}% increase**.")
else:
    st.info("No seasonal data available.")

st.markdown("---")

# ── Zone Comparison ────────────────────────────────────────────
st.subheader("🗺️ Zone-wise Comparison")
with st.spinner("Loading zone data..."):
    zones = api.get_zones()

if zones:
    col1, col2 = st.columns([3, 2])
    with col1:
        st.plotly_chart(zone_bar_chart(zones), use_container_width=True)
    with col2:
        df_z = pd.DataFrame(zones)
        if not df_z.empty:
            col_map_z = {
                "zone": "Zone",
                "avg_delay_minutes": "Avg Delay (min)",
                "otp_percentage": "OTP %",
                "total_records": "Records",
                "severe_count": "Severe",
            }
            cols_z = [c for c in col_map_z if c in df_z.columns]
            st.dataframe(df_z[cols_z].rename(columns=col_map_z),
                         use_container_width=True, hide_index=True)
else:
    st.info("No zone data available.")

st.markdown("---")

# ── Station Heatmap ────────────────────────────────────────────
st.subheader("🗺️ Station Delay Heatmap")
st.caption("Circle size and color indicates average delay — larger and redder = more delayed")

with st.spinner("Loading heatmap data..."):
    heatmap_pts = api.get_heatmap()

if heatmap_pts:
    station_heatmap(heatmap_pts, height=450)
else:
    st.info("No heatmap data available. Station coordinates may be missing.")