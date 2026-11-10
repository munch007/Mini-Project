"""journey.py - plans a trip: direct bus, or two buses with one change.

Timings come from the GTFS schedule. Times after the first stop are ESTIMATES
(the data creator assumed an average bus speed), so we call them 'estimated'.
"""
import numpy as np
import pandas as pd

from route_stats import haversine

WALK_KMH = 4.5          # walking speed for a change
MAX_WALK_KM = 0.30      # max distance between two stops to count as a change
CHANGE_BUFFER_S = 180   # extra safety time when changing buses
CELL = 0.003            # grid size (~330 m) used to find nearby stops quickly


def hms_to_sec(t):
    """'08:30:00' -> seconds. Works for times past 24:00 too."""
    h, m, s = str(t).split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def sec_to_hm(sec):
    """seconds -> '09:05' (wraps past midnight)."""
    sec = int(sec) % 86400
    return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}"


def build_network(data, route_stops):
    """Prepare every route+direction as fast arrays. Call once and cache it."""
    short = dict(zip(data["routes"]["route_id"].astype(str), data["routes"]["route_short_name"].astype(str)))
    long_ = dict(zip(data["routes"]["route_id"].astype(str), data["routes"]["route_long_name"]))

    # departure time of every trip from its first stop
    st = data["stop_times"]
    first = st.loc[st.groupby("trip_id")["stop_sequence"].idxmin(), ["trip_id", "arrival_time"]]
    first = first.merge(data["trips"][["trip_id", "route_id", "direction_id"]], on="trip_id")
    first["sec"] = first["arrival_time"].map(hms_to_sec)
    starts = {
        (str(r), d): np.sort(g["sec"].values)
        for (r, d), g in first.groupby(["route_id", "direction_id"])
    }

    net = {}
    for (rid, d), g in route_stops.groupby(["route_id", "direction_id"]):
        g = g.sort_values("stop_sequence")
        secs = g["arrival_time"].map(hms_to_sec).values
        net[(str(rid), d)] = {
            "short": short.get(str(rid), str(rid)),
            "long": long_.get(str(rid), ""),
            "ids": g["stop_id"].values,
            "names": g["stop_name"].tolist(),
            "lat": g["stop_lat"].values,
            "lon": g["stop_lon"].values,
            "off": secs - secs[0],                      # seconds after first stop
            "starts": starts.get((str(rid), d), np.array([])),
        }

    # grid index: nearby stops share a grid cell
    cells = {}
    for key, r in net.items():
        for i, (la, lo) in enumerate(zip(r["lat"], r["lon"])):
            cells.setdefault((int(la / CELL), int(lo / CELL)), []).append((key, i))
    return {"routes": net, "cells": cells}


def _next_board(route, idx, ready_sec):
    """First time a bus of this route is at stop `idx` at or after `ready_sec`."""
    times = route["starts"] + route["off"][idx]
    pos = np.searchsorted(times, ready_sec)
    return None if pos >= len(times) else int(times[pos])


def _matches(route, id_set):
    return np.isin(route["ids"], list(id_set))


def plan_journeys(network, from_ids, to_ids, depart_sec, max_results=5):
    """Return the best journeys (direct first, then one change), earliest arrival first."""
    net, cells = network["routes"], network["cells"]
    plans = []
    ends_a, ends_b = {}, {}
    for key, r in net.items():
        ma, mb = _matches(r, from_ids), _matches(r, to_ids)
        if ma.any():
            ends_a[key] = int(np.argmax(ma))                 # first stop in area A
        if mb.any():
            ends_b[key] = int(np.argmax(mb))                 # first stop in area B

    # ---- direct buses ----
    for key, ia in ends_a.items():
        if key not in ends_b:
            continue
        r = net[key]
        mb = _matches(r, to_ids)
        later = np.where(mb & (np.arange(len(mb)) > ia))[0]
        if len(later) == 0:
            continue
        ib = int(later[0])
        board = _next_board(r, ia, depart_sec)
        if board is None:
            continue
        ride = int(r["off"][ib] - r["off"][ia])
        plans.append({
            "changes": 0, "arrive": board + ride, "board": board,
            "legs": [{"bus": r["short"], "route": r["long"], "from": r["names"][ia], "to": r["names"][ib],
                      "stops": ib - ia, "depart": board, "arrive": board + ride}],
        })

    # ---- one change ----
    best = {}
    for k1, ia in ends_a.items():
        r1 = net[k1]
        for x in range(ia + 1, len(r1["ids"])):
            if r1["ids"][x] in from_ids or r1["ids"][x] in to_ids:
                continue
            cx, cy = int(r1["lat"][x] / CELL), int(r1["lon"][x] / CELL)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for (k2, y) in cells.get((cx + dx, cy + dy), []):
                        ib = ends_b.get(k2)
                        if ib is None or y >= ib or net[k2]["short"] == r1["short"]:
                            continue
                        r2 = net[k2]
                        if r2["ids"][y] in to_ids:
                            continue
                        walk = haversine(r1["lat"][x], r1["lon"][x], r2["lat"][y], r2["lon"][y])
                        if walk > MAX_WALK_KM:
                            continue
                        ride1 = r1["off"][x] - r1["off"][ia]
                        ride2 = r2["off"][ib] - r2["off"][y]
                        cost = ride1 + ride2 + walk / WALK_KMH * 3600
                        pair = (r1["short"], r2["short"])
                        if pair not in best or cost < best[pair][0]:
                            best[pair] = (cost, k1, ia, x, k2, y, ib, walk)

    for pair, (cost, k1, ia, x, k2, y, ib, walk) in sorted(best.items(), key=lambda kv: kv[1][0])[:40]:
        r1, r2 = net[k1], net[k2]
        board1 = _next_board(r1, ia, depart_sec)
        if board1 is None:
            continue
        arrive_x = board1 + int(r1["off"][x] - r1["off"][ia])
        ready = arrive_x + int(walk / WALK_KMH * 3600) + CHANGE_BUFFER_S
        board2 = _next_board(r2, y, ready)
        if board2 is None:
            continue
        arrive = board2 + int(r2["off"][ib] - r2["off"][y])
        plans.append({
            "changes": 1, "arrive": arrive, "board": board1, "walk_m": int(walk * 1000),
            "legs": [
                {"bus": r1["short"], "route": r1["long"], "from": r1["names"][ia], "to": r1["names"][x],
                 "stops": x - ia, "depart": board1, "arrive": arrive_x},
                {"bus": r2["short"], "route": r2["long"], "from": r2["names"][y], "to": r2["names"][ib],
                 "stops": ib - y, "depart": board2, "arrive": arrive},
            ],
        })

    # direct journeys first, then by earliest arrival
    plans.sort(key=lambda p: (p["changes"] > 0 and any(q["changes"] == 0 for q in plans) and p["arrive"] > min(
        q["arrive"] for q in plans if q["changes"] == 0) + 1800, p["arrive"], p["changes"]))
    seen, out = set(), []
    for p in plans:
        sig = tuple(l["bus"] for l in p["legs"])
        if sig in seen:
            continue
        seen.add(sig)
        out.append(p)
    return out[:max_results]


def describe(plan):
    """Plain-English steps for one journey."""
    lines = []
    for n, leg in enumerate(plan["legs"], 1):
        lines.append(
            f"{n}. Board bus **{leg['bus']}** at **{leg['from']}** at about {sec_to_hm(leg['depart'])}. "
            f"Get off at **{leg['to']}** ({leg['stops']} stops, about {sec_to_hm(leg['arrive'])})."
        )
        if n < len(plan["legs"]):
            lines.append(f"   Walk about {plan['walk_m']} m to the next stop and wait for the next bus.")
    return lines
