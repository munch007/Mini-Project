"""route_stats.py - route statistics, distances and route matching."""
from math import radians, sin, cos, asin, sqrt
import pandas as pd


def haversine(lat1, lon1, lat2, lon2):
    """Distance in km between two latitude/longitude points."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def build_route_stops(data):
    """For every (route, direction) pick the longest trip and list its stops in order.

    Returns a table: route_id, direction_id, stop_sequence, stop_name,
    stop_lat, stop_lon, cum_km (distance travelled from the first stop).
    """
    trips, stop_times, stops = data["trips"], data["stop_times"], data["stops"]

    # number of stops in each trip
    trip_len = stop_times.groupby("trip_id").size().rename("n_stops").reset_index()
    t = trips.merge(trip_len, on="trip_id")

    # longest trip for each route + direction
    t = t.sort_values("n_stops", ascending=False)
    best = t.drop_duplicates(subset=["route_id", "direction_id"])

    rows = stop_times.merge(best[["trip_id", "route_id", "direction_id"]], on="trip_id")
    rows = rows.merge(stops, on="stop_id")
    rows = rows.sort_values(["route_id", "direction_id", "stop_sequence"]).reset_index(drop=True)

    # distance from previous stop, then running total per route+direction
    grp = rows.groupby(["route_id", "direction_id"])
    prev_lat = grp["stop_lat"].shift()
    prev_lon = grp["stop_lon"].shift()
    seg = []
    for la, lo, pla, plo in zip(rows.stop_lat, rows.stop_lon, prev_lat, prev_lon):
        seg.append(0.0 if pd.isna(pla) else haversine(pla, plo, la, lo))
    rows["seg_km"] = seg
    rows["cum_km"] = rows.groupby(["route_id", "direction_id"])["seg_km"].cumsum()
    return rows


def count_trips(data):
    """Number of trips per route + direction (a measure of how frequent a route is)."""
    return (data["trips"].groupby(["route_id", "direction_id"]).size()
            .rename("trips").reset_index())


def overview_table(data, route_stops):
    """One row per route: name, number of stops, length in km, trips.

    n_stops and length_km describe ONE direction (the longer one). Counting both
    directions together would double-count the same physical stops.
    """
    per_direction = route_stops.groupby(["route_id", "direction_id"]).agg(
        n_stops=("stop_sequence", "size"), length_km=("cum_km", "max")
    ).reset_index()
    longest = per_direction.groupby("route_id").agg(
        n_stops=("n_stops", "max"), length_km=("length_km", "max")
    ).reset_index()
    trips = data["trips"].groupby("route_id").size().rename("trips").reset_index()
    out = data["routes"].merge(longest, on="route_id").merge(trips, on="route_id")
    return out.sort_values("n_stops", ascending=False).reset_index(drop=True)

def routes_between(data, route_stops, area_a, area_b):
    """Find routes that pass an area matching `area_a` and later an area matching `area_b`.

    Matching is by text (case-insensitive), e.g. 'swargate' and 'katraj'.
    Returns: route name, stops between, distance between (km), trips.
    """
    a, b = area_a.strip().lower(), area_b.strip().lower()
    trip_counts = count_trips(data)
    names = data["routes"].set_index("route_id")["route_long_name"].to_dict()
    results = []

    for (route_id, direction), g in route_stops.groupby(["route_id", "direction_id"]):
        lower = g["stop_name"].str.lower().tolist()
        pos_a = [i for i, n in enumerate(lower) if a in n]
        if not pos_a:
            continue
        i = pos_a[0]                      # first stop matching A
        pos_b = [j for j, n in enumerate(lower) if b in n and j > i]
        if not pos_b:
            continue
        j = pos_b[0]                      # first stop matching B after A
        km = g["cum_km"].iloc[j] - g["cum_km"].iloc[i]
        results.append({
            "route_id": route_id,
            "direction_id": direction,
            "route_name": names.get(route_id, route_id),
            "board_at": g["stop_name"].iloc[i],
            "get_off_at": g["stop_name"].iloc[j],
            "stops_between": j - i,
            "distance_km": round(km, 2),
        })

    df = pd.DataFrame(results)
    if df.empty:
        return df
    df = df.merge(trip_counts, on=["route_id", "direction_id"], how="left")
    return df.reset_index(drop=True)
