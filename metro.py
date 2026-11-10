"""metro.py - simple Pune Metro (Purple + Aqua line) suggestions.

IMPORTANT: no open Pune Metro GTFS was found, so this uses a hand-made station list
(data/metro_stations.csv, compiled from the Pune Metro project profile) and only
counts stations. It has NO timings. Always tell the user to check Maha Metro for times.
Range Hill (Purple) and planned extensions are left out. Verify the list before the demo.
"""
import pandas as pd

INTERCHANGE = "District Court (Civil Court)"   # where Purple and Aqua meet


def load_metro(path="data/metro_stations.csv"):
    df = pd.read_csv(path)
    df["keys"] = df["keywords"].str.lower().str.split(";")
    return df


def stations_near(place, metro):
    """Metro rows whose keywords appear in the place name (or the other way round)."""
    p = place.lower()
    hit = metro[metro["keys"].apply(lambda ks: any(k in p or p in k for k in ks))]
    return hit


def metro_options(from_place, to_place, metro):
    """List of metro suggestions: same line, or one change at the interchange."""
    a, b = stations_near(from_place, metro), stations_near(to_place, metro)
    if a.empty or b.empty:
        return []
    out = []
    for _, ra in a.iterrows():
        for _, rb in b.iterrows():
            if ra["station"] == rb["station"]:
                continue
            if ra["line"] == rb["line"]:
                out.append({"text": f"{ra['line']} Line: {ra['station']} to {rb['station']} "
                                    f"({abs(int(ra['order']) - int(rb['order']))} stations)"})
            else:
                ia = metro[(metro.line == ra["line"]) & (metro.station == INTERCHANGE)]["order"]
                ib = metro[(metro.line == rb["line"]) & (metro.station == INTERCHANGE)]["order"]
                if len(ia) and len(ib):
                    n1 = abs(int(ra["order"]) - int(ia.iloc[0]))
                    n2 = abs(int(rb["order"]) - int(ib.iloc[0]))
                    out.append({"text": f"{ra['line']} Line from {ra['station']} to {INTERCHANGE} ({n1} stations), "
                                        f"change, then {rb['line']} Line to {rb['station']} ({n2} stations)"})
    seen, uniq = set(), []
    for o in out:
        if o["text"] not in seen:
            seen.add(o["text"])
            uniq.append(o)
    return uniq[:3]
