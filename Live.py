"""live.py - optional live bus positions (experimental).

Data source: the unofficial Chartr / Aapli-PMPML API documented in
croyla/pmpml-gtfs (api-doc.yaml). It is NOT an official PMPML feed, may need
a key, may change or stop without notice, and only buses fitted with tracking
devices appear. Every function therefore fails safely: the app keeps working
with scheduled times if live data is unavailable.
"""
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import pandas as pd

from route_stats import haversine
from journey import hms_to_sec, sec_to_hm

BASE_URL = "https://prod-pmpml-routesapi.chartr.in"
STALE_SECONDS = 300          # a position older than 5 minutes is shown as 'stale'
TIMEOUT_S = 8
MAX_MATCH_DELAY_S = 45 * 60  # if no scheduled trip is within 45 min, we do not claim a delay

# The API's UP/DOWN labels are the REVERSE of the GTFS ones. Checked on the API's own
# route list: '44UP' runs Katraj -> Akurdi, but GTFS route 44 (UP, direction_id 0) runs
# Akurdi -> Katraj. Same pattern for 281 and 43A. So API UP = our direction_id 1.
API_LABEL_TO_DIRECTION = {"UP": 1, "DOWN": 0}
DIRECTION_TO_API_LABEL = {1: "UP", 0: "DOWN"}


class LiveError(Exception):
    """Live data could not be fetched (network, blocked, bad response)."""


def fetch_buses_on_route(route_long_name, timeout=TIMEOUT_S):
    """POST /buses-on-route for one name such as '256UP'. Returns a list of dicts."""
    try:
        r = requests.post(f"{BASE_URL}/buses-on-route",
                          json={"route_long_name": route_long_name}, timeout=timeout)
        r.raise_for_status()
        body = r.json()
    except (requests.RequestException, ValueError) as e:
        raise LiveError(f"live service unavailable ({e.__class__.__name__})") from e
    return body.get("data") or []


def clean_buses(raw, now=None):
    """Raw API rows -> tidy table with numeric lat/lon, age in seconds and a stale flag."""
    now = time.time() if now is None else now
    cols = ["bus_id", "route", "direction_id", "lat", "lon", "age_s", "stale"]
    rows = []
    for b in raw:
        try:
            lat, lon, ts = float(b["lat"]), float(b["lon"]), float(b["timestamp"])
        except (KeyError, TypeError, ValueError):
            continue                      # skip malformed rows
        if not (18.0 < lat < 19.2 and 73.0 < lon < 74.5):
            continue                      # outside the Pune region -> bad GPS fix
        age = max(0.0, now - ts)
        name = str(b.get("route", "?"))
        label = "UP" if name.endswith("UP") else "DOWN" if name.endswith("DOWN") else None
        rows.append({"bus_id": b.get("id", "?"), "route": name,
                     "direction_id": API_LABEL_TO_DIRECTION.get(label),
                     "lat": lat, "lon": lon, "age_s": age, "stale": age > STALE_SECONDS})
    return pd.DataFrame(rows, columns=cols)


def live_for_route(short_name):
    """Live buses for both directions of a route number (e.g. '44' -> 44UP + 44DOWN)."""
    raw, errors = [], 0
    for suffix in ("UP", "DOWN"):
        try:
            raw += fetch_buses_on_route(f"{short_name}{suffix}")
        except LiveError:
            errors += 1
    if errors == 2:
        raise LiveError("live service unavailable")
    return clean_buses(raw)


def nearest_index(bus_lat, bus_lon, route_stops):
    """Position (0-based) in the stop list of the stop closest to the bus."""
    d = [haversine(bus_lat, bus_lon, la, lo)
         for la, lo in zip(route_stops.stop_lat, route_stops.stop_lon)]
    return min(range(len(d)), key=d.__getitem__)


def nearest_stop_name(bus_lat, bus_lon, route_stops):
    """Name of the stop closest to a bus (route_stops needs stop_name, stop_lat, stop_lon)."""
    return route_stops.stop_name.iloc[nearest_index(bus_lat, bus_lon, route_stops)]


# ---------------- arrival times and delay ----------------

def now_seconds_ist():
    """Seconds since midnight in Pune (IST), independent of the server's time zone."""
    n = datetime.now(ZoneInfo("Asia/Kolkata"))
    return n.hour * 3600 + n.minute * 60 + n.second


def schedule_table(data, route_id, direction_id):
    """Scheduled time (seconds) at every stop for every trip of one route + direction.

    Rows = trips, columns = stop_id. Times after the first stop are estimates."""
    trips = data["trips"]
    ids = trips[(trips["route_id"].astype(str) == str(route_id)) &
                (trips["direction_id"] == direction_id)]["trip_id"]
    st = data["stop_times"]
    st = st[st["trip_id"].isin(ids)].dropna(subset=["arrival_time"]).copy()
    st["sec"] = st["arrival_time"].map(hms_to_sec)
    return st.pivot_table(index="trip_id", columns="stop_id", values="sec", aggfunc="first")


def next_scheduled(sched, ref, board_idx, now_sec, n=4):
    """Next n scheduled times at the boarding stop (as 'HH:MM'). Used when no live bus is usable."""
    sid = ref.stop_id.iloc[board_idx]
    if sid not in sched.columns:
        return []
    times = sorted(t for t in sched[sid].dropna() if t >= now_sec)
    return [sec_to_hm(t) for t in times[:n]]


def arrival_board(sched, ref, live, board_idx, now_sec):
    """For each fresh live bus that has NOT yet passed the boarding stop, work out:
      - how many stops away it is,
      - the minutes until it reaches the stop (the scheduled running time from its position),
      - the delay: now minus the scheduled time at the bus's stop, using the closest
        scheduled trip. Delay is approximate (+ = late, - = early).
    ref = stops of ONE direction in order; live = clean_buses() output for that direction."""
    board_id = ref.stop_id.iloc[board_idx]
    cols = ["bus_id", "stops_away", "near_stop", "eta_min", "expected", "scheduled",
            "delay_min", "last_seen_s"]
    rows = []
    if board_id not in sched.columns:
        return pd.DataFrame(rows, columns=cols)
    for _, b in live.iterrows():
        if b.stale:
            continue                               # old position: do not trust it
        i = nearest_index(b.lat, b.lon, ref)
        if i > board_idx:
            continue                               # bus already passed this stop
        bus_id_ = ref.stop_id.iloc[i]
        if bus_id_ not in sched.columns:
            continue
        pair = sched[[bus_id_, board_id]].dropna()
        pair = pair[pair[board_id] >= pair[bus_id_]]
        if pair.empty:
            continue
        # closest scheduled trip to 'now' at the bus's stop (also try after-midnight times)
        best = None
        for now_c in (now_sec, now_sec + 86400):
            diff = (now_c - pair[bus_id_]).abs()
            k = diff.idxmin()
            if best is None or diff[k] < best[0]:
                best = (diff[k], k, now_c)
        _, k, now_c = best
        t_bus, t_board = pair.loc[k, bus_id_], pair.loc[k, board_id]
        run = t_board - t_bus
        delay = now_c - t_bus
        rows.append({
            "bus_id": b.bus_id,
            "stops_away": board_idx - i,
            "near_stop": ref.stop_name.iloc[i],
            "eta_min": round(run / 60),
            "expected": sec_to_hm(now_c + run),
            "scheduled": sec_to_hm(t_board),
            "delay_min": round(delay / 60) if abs(delay) <= MAX_MATCH_DELAY_S else None,
            "last_seen_s": int(b.age_s),
        })
    return pd.DataFrame(rows, columns=cols).sort_values("eta_min").reset_index(drop=True)
