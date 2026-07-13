# dashboard/components/maps.py
import folium
from streamlit_folium import st_folium


def station_heatmap(points: list, height: int = 420):
    """
    Render a Folium map with station circles colored by avg delay.
    points: [{"station_code","station_name","latitude","longitude","value","total_trains"}]
    """
    m = folium.Map(
        location=[22.5, 80.0],
        zoom_start=5,
        tiles="CartoDB positron",
    )

    if not points:
        st_folium(m, height=height, use_container_width=True)
        return

    max_val = max(p.get("value", 0) for p in points) or 1

    for p in points:
        lat = p.get("latitude")
        lng = p.get("longitude")
        if not lat or not lng:
            continue

        val  = p.get("value", 0)
        norm = val / max_val

        # Color scale: green → yellow → red
        if norm < 0.33:
            color = "#22C55E"
        elif norm < 0.66:
            color = "#EAB308"
        else:
            color = "#EF4444"

        radius = max(6, min(20, norm * 18 + 5))

        folium.CircleMarker(
            location=[lat, lng],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            popup=folium.Popup(
                f"""
                <b>{p.get('station_name','')}</b> ({p.get('station_code','')})<br>
                Avg Delay: <b>{val:.1f} min</b><br>
                Train passes: {p.get('total_trains', 0):,}
                """,
                max_width=200,
            ),
            tooltip=f"{p.get('station_code','')} — {val:.1f} min",
        ).add_to(m)

    # Legend
    legend_html = """
    <div style="position:fixed;bottom:30px;left:30px;z-index:999;background:white;
                padding:10px 14px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.15);
                font-size:12px">
        <b>Avg Delay</b><br>
        <span style="color:#22C55E">●</span> Low (&lt;33%)<br>
        <span style="color:#EAB308">●</span> Medium<br>
        <span style="color:#EF4444">●</span> High (&gt;66%)
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    st_folium(m, height=height, use_container_width=True)


def anomaly_map(anomalies: list, height: int = 380):
    """Map showing anomaly locations as pulsing markers."""
    m = folium.Map(
        location=[22.5, 80.0],
        zoom_start=5,
        tiles="CartoDB dark_matter",
    )

    severity_colors = {
        "CRITICAL": "#EF4444",
        "HIGH":     "#F97316",
        "MEDIUM":   "#EAB308",
        "LOW":      "#22C55E",
    }

    for a in anomalies[:50]:  # Cap at 50 markers
        # We don't have lat/lng directly in anomaly, skip if station has no coords
        # In a real setup you'd join with station data
        pass

    st_folium(m, height=height, use_container_width=True)