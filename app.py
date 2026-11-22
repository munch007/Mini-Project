"""app.py - Streamlit dashboard for Pune CommuteWise.

Run with:  streamlit run app.py
"""
import datetime
import pandas as pd
import streamlit as st
import plotly.express as px

from data_loader import load_gtfs
from route_stats import build_route_stops, overview_table, routes_between
from scoring import add_convenience_score, recommendation_text
from places import build_places, resolve_place, ALIASES
from journey import build_network, plan_journeys, describe, sec_to_hm
from metro import load_metro, metro_options
from live import (live_for_route, nearest_stop_name, LiveError, schedule_table,
                  arrival_board, next_scheduled, now_seconds_ist)

st.set_page_config(page_title="Pune CommuteWise", layout="wide")


@st.cache_data
def prepare():
    """Load and prepare everything once (cached so the app stays fast)."""
    data = load_gtfs("data")
    route_stops = build_route_stops(data)
    overview = overview_table(data, route_stops)
    network = build_network(data, route_stops)
    places = sorted(set(build_places(route_stops)) | set(ALIASES), key=str.lower)
    metro = load_metro("data/metro_stations.csv")
    return data, route_stops, overview, network, places, metro


data, route_stops, overview, network, places, metro = prepare()

st.title("Pune CommuteWise")
st.caption("Plan a PMPML bus journey. Data: croyla/pmpml-gtfs. Times after the first stop are estimates.")

tab0, tab1, tab2, tab3, tab4 = st.tabs(["Journey planner", "Overview", "Route explorer", "Compare routes", "Live buses (experimental)"])


@st.cache_data(ttl=15)
def get_live(short_name):
    """Live buses, cached for 15 s so we do not hammer the service."""
    return live_for_route(short_name)

# ---------- Screen 0: Journey planner ----------
with tab0:
    st.write("Pick where you are and where you want to go. Type in the box to search.")
    c1, c2, c3 = st.columns([2, 2, 1])
    start = c1.selectbox("From", places, index=places.index("Katraj") if "Katraj" in places else 0)
    end = c2.selectbox("To", places, index=places.index("Hadapsar Gadital") if "Hadapsar Gadital" in places else 1)
    leave = c3.time_input("Leave at", datetime.time(9, 0))

    if st.button("Plan my journey", type="primary"):
        if start == end:
            st.warning("From and To are the same place. Please choose two different places.")
        else:
            from_ids = resolve_place(start, data["stops"])
            to_ids = resolve_place(end, data["stops"])
            depart = leave.hour * 3600 + leave.minute * 60
            plans = plan_journeys(network, from_ids, to_ids, depart)

            if not plans:
                st.error("No bus journey found with at most one change. Try a nearby place or a different time.")
            for i, p in enumerate(plans, 1):
                kind = "Direct bus" if p["changes"] == 0 else "1 change"
                total = (p["arrive"] - depart) // 60
                with st.expander(f"Option {i}: {kind}  |  arrive about {sec_to_hm(p['arrive'])}  |  about {total} min from {sec_to_hm(depart)}", expanded=(i == 1)):
                    for line in describe(p):
                        st.markdown(line)

            m = metro_options(start, end, metro)
            if m:
                st.subheader("Metro option")
                for o in m:
                    st.markdown("- " + o["text"])
                st.caption("Metro timings are not in our data. Please check the Maha Metro app for train times.")
            st.caption("Times are estimates from the PMPML schedule data, not live bus positions.")

# ---------- Screen 1: Overview ----------
with tab1:
    c1, c2, c3 = st.columns(3)
    c1.metric("Total routes", len(overview))
    c2.metric("Total stops", data["stops"]["stop_id"].nunique())
    c3.metric("Average stops per route", round(overview["n_stops"].mean(), 1))
    top = overview.head(10)
    fig = px.bar(top, x="route_long_name", y="n_stops", title="10 routes with the most stops",
                 labels={"route_long_name": "Route", "n_stops": "Number of stops"})
    st.plotly_chart(fig)

# ---------- Screen 2: Route explorer ----------
with tab2:
    choice = st.selectbox("Select a route", overview["route_long_name"])
    row = overview[overview["route_long_name"] == choice].iloc[0]
    st.write(f"**Stops:** {row['n_stops']}  |  **Length:** {row['length_km']:.1f} km  |  **Trips:** {row['trips']}")
    stops_of_route = route_stops[route_stops["route_id"] == row["route_id"]]
    first_dir = stops_of_route["direction_id"].iloc[0]
    stops_of_route = stops_of_route[stops_of_route["direction_id"] == first_dir]
    if hasattr(px, "line_map"):
        fig = px.line_map(stops_of_route, lat="stop_lat", lon="stop_lon", hover_name="stop_name", zoom=10, height=450)
    else:
        fig = px.line_mapbox(stops_of_route, lat="stop_lat", lon="stop_lon", hover_name="stop_name",
                             zoom=10, height=450, mapbox_style="open-street-map")
    st.plotly_chart(fig)
    st.dataframe(stops_of_route[["stop_sequence", "stop_name"]], hide_index=True)

# ---------- Screen 3: Compare routes ----------
with tab3:
    col_a, col_b = st.columns(2)
    area_a = col_a.text_input("From (part of a stop name)", "Swargate")
    area_b = col_b.text_input("To (part of a stop name)", "Katraj")
    if st.button("Find routes"):
        if not area_a.strip() or not area_b.strip():
            st.warning("Please enter both areas.")
        else:
            found = routes_between(data, route_stops, area_a, area_b)
            if found.empty:
                st.warning("No direct route found. Try different or shorter names.")
            else:
                scored = add_convenience_score(found)
                st.success(recommendation_text(scored))
                st.dataframe(scored[["route_name", "board_at", "get_off_at", "stops_between",
                                     "distance_km", "trips", "convenience_score"]], hide_index=True)
                fig = px.bar(scored.head(8), x="route_name", y="convenience_score", title="Convenience score",
                             labels={"route_name": "Route", "convenience_score": "Score (0-100)"})
                st.plotly_chart(fig)

# ---------- Screen 4: Live buses (experimental) ----------
@st.cache_data
def get_schedule(route_id, direction_id):
    return schedule_table(data, route_id, direction_id)


with tab4:
    st.caption("Experimental. Live positions come from an unofficial PMPML app service and only cover buses "
               "that have tracking devices. Delay is approximate: it compares the bus with the closest "
               "scheduled trip in our (estimated) timetable.")
    live_choice = st.selectbox("Route", overview["route_long_name"], key="live_route")
    lrow = overview[overview["route_long_name"] == live_choice].iloc[0]
    rid = lrow["route_id"]
    dirs = sorted(route_stops[route_stops["route_id"] == rid]["direction_id"].unique())
    ref_by_dir = {d: route_stops[(route_stops["route_id"] == rid) & (route_stops["direction_id"] == d)]
                  .sort_values("stop_sequence").reset_index(drop=True) for d in dirs}
    d_choice = st.radio("Direction", dirs, horizontal=True, key="live_dir",
                        format_func=lambda d: "Towards " + ref_by_dir[d]["stop_name"].iloc[-1])
    ref = ref_by_dir[d_choice]
    board_name = st.selectbox("Your boarding stop", ref["stop_name"], key="live_stop")
    board_idx = int(ref.index[ref["stop_name"] == board_name][0])

    if st.button("Check bus arrival", key="live_btn"):
        sched = get_schedule(rid, d_choice)
        now_s = now_seconds_ist()
        usable = None
        try:
            live_all = get_live(str(rid))
            live_dir = live_all[live_all["direction_id"] == d_choice]
            usable = arrival_board(sched, ref, live_dir, board_idx, now_s)
        except LiveError:
            live_dir = None

        if usable is not None and not usable.empty:
            first = usable.iloc[0]
            if first["delay_min"] is None or pd.isna(first["delay_min"]):
                status = "could not be compared with our timetable"
            elif first["delay_min"] > 1:
                status = f"running about {int(first['delay_min'])} min late"
            elif first["delay_min"] < -1:
                status = f"running about {int(-first['delay_min'])} min early"
            else:
                status = "running on time"
            st.success(f"Next tracked bus reaches {board_name} in about {int(first['eta_min'])} min "
                       f"(around {first['expected']}). Scheduled: {first['scheduled']}. It is {status}.")
            show = usable.rename(columns={"bus_id": "Bus", "stops_away": "Stops away", "near_stop": "Now near",
                                          "eta_min": "Arrives in (min)", "expected": "Expected",
                                          "scheduled": "Scheduled", "delay_min": "Delay (min)",
                                          "last_seen_s": "Position age (s)"})
            st.dataframe(show, hide_index=True)
            pos = live_dir.copy()
            if hasattr(px, "scatter_map"):
                fig = px.scatter_map(pos, lat="lat", lon="lon", hover_name="bus_id", zoom=10, height=400)
            else:
                fig = px.scatter_mapbox(pos, lat="lat", lon="lon", hover_name="bus_id", zoom=10, height=400,
                                        mapbox_style="open-street-map")
            st.plotly_chart(fig)
        else:
            st.info("Live position is not available for this stop right now. Only some buses are tracked, "
                    "and the live service can be down, so this does not mean that no bus is coming. "
                    "Please use the scheduled times below.")
            upcoming = next_scheduled(sched, ref, board_idx, now_s)
            if upcoming:
                st.write(f"**Next scheduled buses at {board_name}:** " + ", ".join(upcoming) +
                         "  (estimated timetable)")
            else:
                st.write("No more scheduled buses today in our timetable for this stop.")
