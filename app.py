"""app.py - Streamlit dashboard for Pune CommuteWise.

Run with:  streamlit run app.py
"""
import streamlit as st
import plotly.express as px

from data_loader import load_gtfs
from route_stats import build_route_stops, overview_table, routes_between
from scoring import add_convenience_score, recommendation_text

st.set_page_config(page_title="Pune CommuteWise", layout="wide")


@st.cache_data
def prepare():
    """Load and prepare everything once (cached so the app stays fast)."""
    data = load_gtfs("data")
    route_stops = build_route_stops(data)
    overview = overview_table(data, route_stops)
    return data, route_stops, overview


data, route_stops, overview = prepare()

st.title("Pune CommuteWise")
st.caption("Compare PMPML bus routes. Data: croyla/pmpml-gtfs (travel times are estimates).")

tab1, tab2, tab3 = st.tabs(["Overview", "Route explorer", "Compare routes"])

# ---------- Screen 1: Overview ----------
with tab1:
    c1, c2, c3 = st.columns(3)
    c1.metric("Total routes", len(overview))
    c2.metric("Total stops", data["stops"]["stop_id"].nunique())
    c3.metric("Average stops per route", round(overview["n_stops"].mean(), 1))
    top = overview.head(10)
    fig = px.bar(top, x="route_long_name", y="n_stops", title="10 routes with the most stops")
    st.plotly_chart(fig)

# ---------- Screen 2: Route explorer ----------
with tab2:
    choice = st.selectbox("Select a route", overview["route_long_name"])
    row = overview[overview["route_long_name"] == choice].iloc[0]
    st.write(f"**Stops:** {row['n_stops']}  |  **Length:** {row['length_km']:.1f} km  |  **Trips:** {row['trips']}")
    stops_of_route = route_stops[route_stops["route_id"] == row["route_id"]]
    first_dir = stops_of_route["direction_id"].iloc[0]
    stops_of_route = stops_of_route[stops_of_route["direction_id"] == first_dir]
    fig = px.line_map(stops_of_route, lat="stop_lat", lon="stop_lon", hover_name="stop_name", zoom=10, height=450) \
        if hasattr(px, "line_map") else px.line_mapbox(stops_of_route, lat="stop_lat", lon="stop_lon",
                                                         hover_name="stop_name", zoom=10, height=450,
                                                         mapbox_style="open-street-map")
    st.plotly_chart(fig)
    st.dataframe(stops_of_route[["stop_sequence", "stop_name"]])

# ---------- Screen 3: Compare routes ----------
with tab3:
    col_a, col_b = st.columns(2)
    area_a = col_a.text_input("From (part of a stop name)", "Swargate")
    area_b = col_b.text_input("To (part of a stop name)", "Katraj")
    if st.button("Find routes"):
        found = routes_between(data, route_stops, area_a, area_b)
        if found.empty:
            st.warning("No direct route found. Try different or shorter names.")
        else:
            scored = add_convenience_score(found)
            st.success(recommendation_text(scored))
            st.dataframe(scored[["route_name", "board_at", "get_off_at", "stops_between",
                                 "distance_km", "trips", "convenience_score"]])
            fig = px.bar(scored.head(8), x="route_name", y="convenience_score", title="Convenience score")
            st.plotly_chart(fig)
