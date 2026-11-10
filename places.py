"""places.py - turns thousands of stop names into a short list of places people know.

Problem: the data has 3,800+ stop names (Katraj Dairy, Katraj Sarpodyan...).
A passenger just thinks "Katraj". So we:
  1. build a list of well-served places (stops many routes pass through)
  2. when a place is chosen, collect ALL nearby stops whose name contains it.
"""
import re
import numpy as np

from route_stats import haversine

# Names people use that are not stop names -> the place whose stops we use.
# Add more here (a good task for a team member!). Keep the values as real place names.
ALIASES = {
    "MIT-WPU (Kothrud)": "Kothrud",
    "Pune Railway Station": "Pune Station",
    "Pune Airport (Lohegaon)": "Lohegaon Airport",
    "Shivajinagar": "Shivaji Nagar",
    "Hinjewadi": "Hinjawadi",
    "Civil Court / District Court (Metro)": "Shivaji Nagar Civil Court Metro Station",
}


def build_places(route_stops, min_routes=5):
    """List of place names served by at least `min_routes` routes (sorted A-Z)."""
    counts = route_stops.groupby("stop_name")["route_id"].nunique()
    names = counts[counts >= min_routes].index.tolist()
    return sorted(set(names), key=str.lower)


def resolve_place(place, stops, radius_km=2.0):
    """Return the set of stop_ids that belong to `place`.

    Rule: stop name contains the place as whole words AND the stop is within
    `radius_km` of the place's main location (so 'Shivaji' in Hinjawadi is ignored).
    """
    place = ALIASES.get(place, place)
    key = place.strip().lower()
    if not key:
        return set()
    names_l = stops["stop_name"].str.lower()
    pattern = r"\b" + re.escape(key) + r"\b"
    cand = stops[names_l.str.contains(pattern, regex=True)]
    if cand.empty:
        return set()
    exact = cand[cand["stop_name"].str.lower() == key]
    centre = exact if not exact.empty else cand
    clat, clon = centre["stop_lat"].mean(), centre["stop_lon"].mean()
    keep = [
        sid for sid, la, lo in zip(cand["stop_id"], cand["stop_lat"], cand["stop_lon"])
        if haversine(clat, clon, la, lo) <= radius_km
    ]
    return set(keep)
