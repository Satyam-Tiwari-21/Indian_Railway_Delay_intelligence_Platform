# dashboard/app.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

st.set_page_config(
    page_title="India Railways Delay Intelligence",
    page_icon="🚂",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stSidebar"] { background: #003580; }
[data-testid="stSidebar"] * { color: white !important; }
[data-testid="stSidebar"] .stButton button {
    background: rgba(255,255,255,0.15);
    border: 1px solid rgba(255,255,255,0.3);
    color: white !important;
    border-radius: 8px;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: rgba(255,255,255,0.25);
}
div[data-testid="metric-container"] {
    background: white;
    border-radius: 10px;
    padding: 1rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
.block-container { padding-top: 1.5rem; }
h1, h2, h3 { color: #003580; }
</style>
""", unsafe_allow_html=True)

from dashboard.components.auth_wall import check_auth, show_login_page, show_sidebar_user

if not check_auth():
    show_login_page()
    st.stop()

with st.sidebar:
    st.markdown("## 🚂 Railways AI")
    st.markdown("**Delay Intelligence Platform**")
    st.markdown("---")
    st.markdown("### Navigation")
    st.page_link("dashboard/pages/01_Home.py",       label="🏠 Home",       icon=None)
    st.page_link("dashboard/pages/02_Analytics.py",  label="📊 Analytics",  icon=None)
    st.page_link("dashboard/pages/03_Prediction.py", label="🤖 Prediction", icon=None)
    st.page_link("dashboard/pages/04_Anomalies.py",  label="🚨 Anomalies",  icon=None)
    st.page_link("dashboard/pages/05_Forecast.py",   label="📈 Forecast",   icon=None)

show_sidebar_user()

st.title("🚂 India Railways Delay Intelligence Platform")
st.markdown("### Welcome! Use the sidebar to navigate between modules.")

col1, col2, col3 = st.columns(3)
with col1:
    st.info("**🏠 Home**\nNetwork-wide KPIs and delay overview")
with col2:
    st.info("**📊 Analytics**\nRoute, zone and seasonal analysis")
with col3:
    st.info("**🤖 Prediction**\nPredict train delays with AI")

col4, col5, _ = st.columns(3)
with col4:
    st.info("**🚨 Anomalies**\nDetected disruptions and alerts")
with col5:
    st.info("**📈 Forecast**\n30-day zone delay forecast")