# dashboard/pages/04_Anomalies.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
from dashboard.components.auth_wall import check_auth, show_sidebar_user
from dashboard.components.charts import anomaly_trend_chart
from dashboard.components.kpi_cards import severity_badge
from dashboard.utils import api_client as api

st.set_page_config(page_title="Anomalies — Railways AI", page_icon="🚨", layout="wide")

if not check_auth():
    st.warning("Please log in first.")
    st.stop()

show_sidebar_user()

st.title("🚨 Anomaly Detection")
st.caption("Unusual delay patterns detected by Isolation Forest + Z-score analysis")

# ── Sidebar filters ────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 Filters")
    severity_filter = st.selectbox("Severity", ["All", "CRITICAL", "HIGH", "MEDIUM", "LOW"])
    show_resolved   = st.checkbox("Show resolved anomalies", value=False)
    limit           = st.slider("Max results", 10, 200, 50)
    refresh         = st.button("🔄 Refresh", use_container_width=True)

sev_param = None if severity_filter == "All" else severity_filter

# Force cache clear on refresh
if refresh:
    api.get_anomaly_feed.clear()

# ── Load data ──────────────────────────────────────────────────
with st.spinner("Loading anomaly feed..."):
    feed = api.get_anomaly_feed(severity=sev_param, resolved=show_resolved, limit=limit)

anomalies     = feed.get("anomalies", [])
critical_cnt  = feed.get("critical_count", 0)
high_cnt      = feed.get("high_count", 0)
medium_cnt    = feed.get("medium_count", 0)
total         = feed.get("total", 0)

# ── Summary badges ─────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Total Open", total, delta=None)
with c2:
    st.metric("🔴 Critical", critical_cnt)
with c3:
    st.metric("🟠 High", high_cnt)
with c4:
    st.metric("🟡 Medium", medium_cnt)

st.markdown("---")

if not anomalies:
    st.success("✅ No anomalies found matching your filters.")
    st.stop()

# ── Anomaly trend chart ────────────────────────────────────────
col_chart, col_info = st.columns([2, 1])
with col_chart:
    st.subheader("📊 Anomalies by Severity")
    st.plotly_chart(anomaly_trend_chart(anomalies), use_container_width=True)

with col_info:
    st.subheader("ℹ️ How it works")
    st.markdown("""
    **Two-stage detection:**
    
    1. **Isolation Forest** — flags statistically unusual delay records based on 20 features
    
    2. **Z-score filter** — cross-checks against each route's own historical baseline (monsoon month, zone, category)
    
    Only records that fail **both** tests are flagged — minimising false positives on structurally late routes.
    """)

st.markdown("---")

# ── Anomaly feed table ─────────────────────────────────────────
st.subheader(f"📋 Anomaly Feed ({len(anomalies)} records)")

role = st.session_state.get("role", "viewer")
can_resolve = role in ("admin", "analyst", "officer")

for i, a in enumerate(anomalies):
    sev   = a.get("severity", "LOW") or "LOW"
    sev_colors = {
        "CRITICAL": "#FEE2E2", "HIGH": "#FFEDD5",
        "MEDIUM": "#FEF9C3",   "LOW": "#F0FDF4",
    }
    bg = sev_colors.get(sev, "#F9FAFB")

    with st.container():
        st.markdown(f"""
        <div style="background:{bg};border-radius:8px;padding:0.8rem 1rem;
                    margin-bottom:0.5rem;border-left:4px solid {'#EF4444' if sev=='CRITICAL' else '#F97316' if sev=='HIGH' else '#EAB308' if sev=='MEDIUM' else '#22C55E'}">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <div>
                    <b>{a.get('train_number','N/A')} — {a.get('train_name','Unknown')}</b>
                    &nbsp; {severity_badge(sev)}
                </div>
                <div style="color:#666;font-size:0.85rem">{a.get('anomaly_date','')}</div>
            </div>
            <div style="margin-top:4px;color:#444;font-size:0.9rem">
                📍 {a.get('station_code','N/A')} &nbsp;|&nbsp;
                Score: {a.get('anomaly_score',0):.3f} &nbsp;|&nbsp;
                Z-score: {a.get('z_score',0) or 0:.1f}σ &nbsp;|&nbsp;
                Type: {a.get('anomaly_type','—') or '—'}
            </div>
            {f'<div style="margin-top:4px;color:#555;font-size:0.85rem">💬 {a.get("explanation","")}</div>' if a.get("explanation") else ""}
        </div>
        """, unsafe_allow_html=True)

        # Resolve button (officers and above)
        if can_resolve and not a.get("is_resolved"):
            col_note, col_btn = st.columns([4, 1])
            with col_note:
                note_key = f"note_{a['id']}_{i}"
                note = st.text_input("Resolution note", key=note_key, label_visibility="collapsed",
                                     placeholder="Enter resolution note...")
            with col_btn:
                if st.button("✅ Resolve", key=f"resolve_{a['id']}_{i}"):
                    if note.strip():
                        with st.spinner("Resolving..."):
                            success = api.resolve_anomaly(a["id"], note)
                        if success:
                            st.success("Anomaly resolved!")
                            api.get_anomaly_feed.clear()
                            st.rerun()
                        else:
                            st.error("Failed to resolve")
                    else:
                        st.warning("Please enter a resolution note")

        if a.get("is_resolved"):
            st.caption(f"✅ Resolved: {a.get('resolution_note','')}")