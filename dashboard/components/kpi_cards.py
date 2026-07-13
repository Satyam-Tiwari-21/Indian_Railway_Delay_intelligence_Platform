# dashboard/components/kpi_cards.py
import streamlit as st


def kpi_card(title: str, value: str, delta: str = "", color: str = "#003580", icon: str = ""):
    """Render a single KPI card with optional delta."""
    delta_html = f'<div style="font-size:0.8rem;color:#888;margin-top:4px">{delta}</div>' if delta else ""
    st.markdown(f"""
    <div style="
        background:white;
        border-left: 4px solid {color};
        border-radius: 8px;
        padding: 1rem 1.2rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        height: 100%;
    ">
        <div style="font-size:0.8rem;color:#666;font-weight:500;text-transform:uppercase;letter-spacing:0.05em">
            {icon} {title}
        </div>
        <div style="font-size:1.9rem;font-weight:700;color:{color};margin-top:4px;line-height:1.1">
            {value}
        </div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def risk_badge(risk_level: str) -> str:
    """Return colored HTML badge for a risk level."""
    colors = {
        "ON_TIME":  ("#EAF3DE", "#3B6D11", "On Time"),
        "SLIGHT":   ("#FEF9C3", "#854D0E", "Slight Delay"),
        "MODERATE": ("#FFEDD5", "#9A3412", "Moderate Delay"),
        "SEVERE":   ("#FEE2E2", "#991B1B", "Severe Delay"),
    }
    bg, fg, label = colors.get(risk_level, ("#F3F4F6", "#374151", risk_level))
    return f'<span style="background:{bg};color:{fg};padding:3px 10px;border-radius:20px;font-size:0.8rem;font-weight:600">{label}</span>'


def severity_badge(severity: str) -> str:
    colors = {
        "CRITICAL": ("#FEE2E2", "#991B1B"),
        "HIGH":     ("#FFEDD5", "#9A3412"),
        "MEDIUM":   ("#FEF9C3", "#854D0E"),
        "LOW":      ("#EAF3DE", "#3B6D11"),
    }
    bg, fg = colors.get(severity, ("#F3F4F6", "#374151"))
    return f'<span style="background:{bg};color:{fg};padding:2px 8px;border-radius:12px;font-size:0.75rem;font-weight:600">{severity}</span>'