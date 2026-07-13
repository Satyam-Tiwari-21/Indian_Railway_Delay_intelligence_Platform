# dashboard/components/charts.py
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

COLORS = {
    "primary": "#003580",
    "orange":  "#FF6B00",
    "green":   "#22C55E",
    "yellow":  "#EAB308",
    "red":     "#EF4444",
    "gray":    "#6B7280",
}

SEASON_COLORS = {
    True:  "#3B82F6",   # Monsoon — blue
    False: "#F97316",   # Normal — orange
}


def delay_trend_chart(data: list) -> go.Figure:
    """Line chart of avg delay by zone over time."""
    if not data:
        return _empty_chart("No trend data available")

    df = pd.DataFrame(data)
    fig = go.Figure()

    if "avg_delay_minutes" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.get("month", range(len(df))),
            y=df["avg_delay_minutes"],
            mode="lines+markers",
            name="Avg Delay",
            line=dict(color=COLORS["primary"], width=2.5),
            marker=dict(size=6),
        ))

    fig.update_layout(
        title="Average Delay by Month",
        xaxis_title="Month",
        yaxis_title="Avg Delay (minutes)",
        template="plotly_white",
        height=320,
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig


def seasonal_chart(data: list) -> go.Figure:
    """Bar chart showing monthly delay pattern with season highlighting."""
    if not data:
        return _empty_chart("No seasonal data available")

    df = pd.DataFrame(data)
    if df.empty or "avg_delay_minutes" not in df.columns:
        return _empty_chart("No seasonal data available")

    colors = []
    for _, row in df.iterrows():
        month = row.get("month", 1)
        if month in [6, 7, 8, 9]:
            colors.append("#3B82F6")   # Monsoon
        elif month in [12, 1]:
            colors.append("#8B5CF6")   # Fog
        elif month in [10, 11]:
            colors.append("#F97316")   # Festive
        else:
            colors.append("#22C55E")   # Normal

    fig = go.Figure(go.Bar(
        x=df.get("month_name", df.get("month", [])),
        y=df["avg_delay_minutes"],
        marker_color=colors,
        text=df["avg_delay_minutes"].round(1),
        textposition="outside",
    ))

    fig.update_layout(
        title="Monthly Delay Pattern",
        xaxis_title="Month",
        yaxis_title="Avg Delay (min)",
        template="plotly_white",
        height=320,
        margin=dict(l=0, r=0, t=40, b=0),
        showlegend=False,
    )

    fig.add_annotation(x=7, y=df["avg_delay_minutes"].max() * 0.9 if len(df) > 0 else 10,
                       text="🌧 Monsoon", showarrow=False, font=dict(color="#3B82F6", size=11))
    return fig


def route_bar_chart(data: list, top_n: int = 15) -> go.Figure:
    """Horizontal bar chart of most delayed routes."""
    if not data:
        return _empty_chart("No route data available")

    df = pd.DataFrame(data[:top_n])
    if df.empty:
        return _empty_chart("No route data available")

    df = df.sort_values("avg_delay_minutes")
    labels = df.apply(
        lambda r: f"{r.get('train_number','')} {r.get('train_name','')[:20]}", axis=1
    )

    fig = go.Figure(go.Bar(
        x=df["avg_delay_minutes"],
        y=labels,
        orientation="h",
        marker_color=COLORS["primary"],
        text=df["avg_delay_minutes"].round(1),
        textposition="outside",
    ))

    fig.update_layout(
        title=f"Top {min(top_n, len(df))} Most Delayed Routes",
        xaxis_title="Avg Delay (minutes)",
        template="plotly_white",
        height=max(300, len(df) * 28),
        margin=dict(l=0, r=20, t=40, b=0),
    )
    return fig


def zone_bar_chart(data: list) -> go.Figure:
    """Bar chart comparing zones by avg delay."""
    if not data:
        return _empty_chart("No zone data")

    df = pd.DataFrame(data).sort_values("avg_delay_minutes", ascending=False)
    if df.empty:
        return _empty_chart("No zone data")

    fig = go.Figure(go.Bar(
        x=df.get("zone", []),
        y=df["avg_delay_minutes"],
        marker_color=COLORS["orange"],
        text=df["avg_delay_minutes"].round(1),
        textposition="outside",
    ))

    fig.update_layout(
        title="Average Delay by Zone",
        xaxis_title="Railway Zone",
        yaxis_title="Avg Delay (min)",
        template="plotly_white",
        height=320,
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig


def otp_donut_chart(otp_pct: float) -> go.Figure:
    """Donut chart showing On-Time Performance."""
    late = max(0, 100 - otp_pct)
    fig = go.Figure(go.Pie(
        values=[otp_pct, late],
        labels=["On Time", "Delayed"],
        hole=0.65,
        marker_colors=[COLORS["green"], "#FCA5A5"],
        textinfo="none",
    ))
    fig.add_annotation(
        text=f"{otp_pct:.1f}%",
        x=0.5, y=0.55, font_size=22, font_color=COLORS["primary"],
        showarrow=False, font=dict(weight="bold"),
    )
    fig.add_annotation(
        text="On Time", x=0.5, y=0.42, font_size=12,
        font_color=COLORS["gray"], showarrow=False,
    )
    fig.update_layout(
        showlegend=False, height=220,
        margin=dict(l=0, r=0, t=10, b=0),
    )
    return fig


def shap_waterfall_chart(explanation: dict, predicted: float) -> go.Figure:
    """Custom SHAP waterfall chart using Plotly."""
    if not explanation:
        return _empty_chart("No explanation available")

    factors = explanation.get("top_factors", explanation.get("factors", []))
    base    = explanation.get("base_value", 18.0)

    if not factors:
        return _empty_chart("No SHAP factors")

    names  = [f.get("display_name", f.get("feature", "")) for f in factors]
    values = [f.get("contribution_minutes", 0) for f in factors]

    names  = ["Base Value"] + names  + ["Prediction"]
    values = [base]         + values + [0]

    colors = []
    for i, v in enumerate(values):
        if i == 0:            colors.append("#6B7280")
        elif i == len(values)-1: colors.append(COLORS["primary"])
        elif v >= 0:          colors.append("#EF4444")
        else:                 colors.append(COLORS["green"])

    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=["absolute"] + ["relative"] * (len(values)-2) + ["total"],
        x=names,
        y=values,
        connector={"line": {"color": "#d0d0d0"}},
        decreasing={"marker": {"color": COLORS["green"]}},
        increasing={"marker": {"color": "#EF4444"}},
        totals={"marker": {"color": COLORS["primary"]}},
        text=[f"+{v:.1f}" if v > 0 else f"{v:.1f}" for v in values],
        textposition="outside",
    ))

    fig.update_layout(
        title=f"Why this prediction? (Predicted: {predicted:.1f} min)",
        template="plotly_white",
        height=380,
        margin=dict(l=0, r=0, t=50, b=0),
        yaxis_title="Delay contribution (minutes)",
    )
    return fig


def forecast_chart(data: list, zone: str) -> go.Figure:
    """Line chart with confidence bands for delay forecast."""
    if not data:
        return _empty_chart("No forecast data available")

    df = pd.DataFrame(data)
    if df.empty or "predicted_avg_delay" not in df.columns:
        return _empty_chart("No forecast data available")

    fig = go.Figure()

    # Confidence band
    if "upper_80" in df.columns and "lower_80" in df.columns:
        fig.add_trace(go.Scatter(
            x=list(df["date"]) + list(df["date"])[::-1],
            y=list(df["upper_80"]) + list(df["lower_80"])[::-1],
            fill="toself",
            fillcolor="rgba(0,53,128,0.1)",
            line=dict(color="rgba(255,255,255,0)"),
            name="80% Confidence Band",
        ))

    # Forecast line
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["predicted_avg_delay"],
        mode="lines+markers",
        name="Predicted Avg Delay",
        line=dict(color=COLORS["primary"], width=2.5),
        marker=dict(size=5),
    ))

    fig.update_layout(
        title=f"30-Day Delay Forecast — {zone} Zone",
        xaxis_title="Date",
        yaxis_title="Avg Delay (min)",
        template="plotly_white",
        height=380,
        margin=dict(l=0, r=0, t=50, b=0),
        legend=dict(orientation="h", y=-0.15),
    )
    return fig


def anomaly_trend_chart(anomalies: list) -> go.Figure:
    """Bar chart of anomaly count by severity."""
    if not anomalies:
        return _empty_chart("No anomaly data")

    sev_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for a in anomalies:
        s = a.get("severity") or "LOW"
        sev_counts[s] = sev_counts.get(s, 0) + 1

    fig = go.Figure(go.Bar(
        x=list(sev_counts.keys()),
        y=list(sev_counts.values()),
        marker_color=["#EF4444", "#F97316", "#EAB308", "#22C55E"],
        text=list(sev_counts.values()),
        textposition="outside",
    ))
    fig.update_layout(
        title="Anomalies by Severity",
        template="plotly_white",
        height=280,
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig


def _empty_chart(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message, x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False, font=dict(size=14, color=COLORS["gray"]),
    )
    fig.update_layout(
        template="plotly_white", height=280,
        margin=dict(l=0, r=0, t=20, b=0),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig