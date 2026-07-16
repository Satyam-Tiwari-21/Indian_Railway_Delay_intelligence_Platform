# dashboard/pages/03_Prediction.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from dashboard.components.auth_wall import check_auth, show_sidebar_user
from dashboard.components.charts import shap_waterfall_chart
from dashboard.components.kpi_cards import risk_badge
from dashboard.utils import api_client as api

st.set_page_config(page_title="Prediction — Railways AI", page_icon="🤖", layout="wide")

if not check_auth():
    st.warning("Please log in first.")
    st.stop()

show_sidebar_user()

role = st.session_state.get("role", "viewer")
if role == "viewer":
    st.error("⛔ Your role (viewer) does not have permission to make predictions. Contact an admin.")
    st.stop()

st.title("🤖 Delay Prediction")
st.caption("Predict arrival delay for any train at any station — powered by XGBoost + SHAP")

# ── Input Form ─────────────────────────────────────────────────
col_form, col_result = st.columns([1, 1], gap="large")

with col_form:
    st.subheader("📋 Prediction Input")
    with st.form("prediction_form"):
        train_number  = st.text_input(
            "Train Number",
            placeholder="e.g. 12301",
            help="5-digit Indian Railways train number",
        )
        station_code  = st.text_input(
            "Query Station Code",
            placeholder="e.g. NDLS, HWH, MAS",
            help="Station code where you want to check the delay",
        ).upper()
        journey_date  = st.date_input(
            "Journey Date",
            value=date.today() + timedelta(days=1),
            min_value=date.today(),
            max_value=date.today() + timedelta(days=90),
        )
        include_shap  = st.checkbox("Show AI explanation (SHAP)", value=True)
        submitted     = st.form_submit_button("🔮 Predict Delay", type="primary", use_container_width=True)

    # Quick reference
    with st.expander("📖 Station code examples"):
        st.markdown("""
        | Code | Station |
        |------|---------|
        | NDLS | New Delhi |
        | HWH  | Howrah Junction |
        | MAS  | Chennai Central |
        | BCT  | Mumbai Central |
        | SBC  | Bengaluru City |
        | ALD  | Prayagraj Jn. |
        | BSB  | Varanasi Jn. |
        | CNB  | Kanpur Central |
        """)

# ── Prediction Result ──────────────────────────────────────────
with col_result:
    st.subheader("📊 Prediction Result")

    if submitted:
        if not train_number:
            st.error("Please enter a train number")
        elif not station_code:
            st.error("Please enter a station code")
        else:
            with st.spinner(f"Predicting delay for train {train_number} at {station_code}..."):
                result = api.predict_delay(train_number, station_code, str(journey_date))

            if result:
                predicted = result.get("predicted_delay_minutes", 0)
                risk      = result.get("risk_level", "ON_TIME")
                lower     = result.get("confidence_lower", 0)
                upper     = result.get("confidence_upper", 0)

                # Risk color
                risk_colors = {
                    "ON_TIME":  "#22C55E",
                    "SLIGHT":   "#EAB308",
                    "MODERATE": "#F97316",
                    "SEVERE":   "#EF4444",
                }
                color = risk_colors.get(risk, "#6B7280")

                # Main result card
                st.markdown(f"""
                <div style="background:{color}15;border:2px solid {color};border-radius:12px;
                            padding:1.5rem;text-align:center;margin-bottom:1rem">
                    <div style="font-size:0.9rem;color:#666;font-weight:500">PREDICTED DELAY</div>
                    <div style="font-size:3rem;font-weight:800;color:{color}">{predicted:.0f}</div>
                    <div style="font-size:1rem;color:#666">minutes</div>
                    <div style="margin-top:0.5rem">{risk_badge(risk)}</div>
                </div>
                """, unsafe_allow_html=True)

                # Details
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("Train", result.get("train_name", train_number)[:25])
                    st.metric("Station", result.get("query_station", station_code))
                with col_b:
                    st.metric("80% Confidence", f"{lower:.0f} – {upper:.0f} min")
                    st.metric("Journey Date", str(journey_date))

                # Class probabilities
                probs = result.get("class_probabilities", {})
                if probs:
                    st.markdown("**Class probabilities:**")
                    prob_cols = st.columns(4)
                    labels = [("ON_TIME","✅","#22C55E"), ("SLIGHT","🟡","#EAB308"),
                              ("MODERATE","🟠","#F97316"), ("SEVERE","🔴","#EF4444")]
                    for col, (key, icon, clr) in zip(prob_cols, labels):
                        with col:
                            val = probs.get(key, 0)
                            st.markdown(f"""
                            <div style="text-align:center;padding:8px;background:{clr}15;
                                        border-radius:8px;border:1px solid {clr}40">
                                <div>{icon}</div>
                                <div style="font-size:1.1rem;font-weight:700;color:{clr}">{val*100:.0f}%</div>
                                <div style="font-size:0.7rem;color:#666">{key.replace('_',' ')}</div>
                            </div>
                            """, unsafe_allow_html=True)

    else:
        st.markdown("""
        <div style="text-align:center;padding:3rem;color:#999">
            <div style="font-size:3rem">🤖</div>
            <div>Fill in the form and click<br><b>Predict Delay</b></div>
        </div>
        """, unsafe_allow_html=True)

# ── SHAP Explanation ───────────────────────────────────────────
if submitted and result and include_shap:
    st.markdown("---")
    st.subheader("🧠 AI Explanation — Why this prediction?")
    explanation = result.get("explanation")
    if explanation:
        st.plotly_chart(
            shap_waterfall_chart(explanation, result.get("predicted_delay_minutes", 0)),
            use_container_width=True,
        )
        st.caption("🔴 Red bars increase the predicted delay | 🟢 Green bars reduce it | Gray = base value")
    else:
        st.info("No explanation available for this prediction.")

st.markdown("---")

# ── Prediction History ─────────────────────────────────────────
st.subheader("📜 Your Recent Predictions")
with st.spinner("Loading history..."):
    history = api.get_prediction_history(limit=10)

if history:
    rows = []
    for p in history:
        rows.append({
            "Train":    p.get("train_number", ""),
            "Station":  p.get("query_station", ""),
            "Date":     p.get("journey_date", ""),
            "Delay":    f"{p.get('predicted_delay_minutes', 0):.0f} min",
            "Risk":     p.get("risk_level", ""),
            "Model":    p.get("model_name", ""),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("No predictions made yet. Make your first prediction above!")