"""scoring.py - convenience score and recommendation text."""

# Our own weights (team model, NOT an official PMPML rating)
WEIGHTS = {"stops": 0.4, "distance": 0.3, "trips": 0.3}


def to_score(series, higher_is_better):
    """Convert a column of numbers to a 0-100 score (min-max scaling)."""
    low, high = series.min(), series.max()
    if high == low:                      # all routes equal -> everyone gets 100
        return series * 0 + 100
    scaled = (series - low) / (high - low) * 100
    return scaled if higher_is_better else 100 - scaled


def add_convenience_score(df):
    """Add stop/distance/trip scores and the final convenience_score (0-100)."""
    df = df.copy()
    df["stops_score"] = to_score(df["stops_between"], higher_is_better=False)
    df["distance_score"] = to_score(df["distance_km"], higher_is_better=False)
    df["trips_score"] = to_score(df["trips"], higher_is_better=True)
    df["convenience_score"] = (
        WEIGHTS["stops"] * df["stops_score"]
        + WEIGHTS["distance"] * df["distance_score"]
        + WEIGHTS["trips"] * df["trips_score"]
    ).round(1)
    return df.sort_values("convenience_score", ascending=False).reset_index(drop=True)


def recommendation_text(df):
    """Plain-English summary of the best routes in a scored table."""
    if df.empty:
        return "No direct route found between these areas."
    best = df.iloc[0]
    text = (f"Route {best['route_name']} has the highest convenience score "
            f"({best['convenience_score']}/100): {int(best['stops_between'])} stops, "
            f"about {best['distance_km']} km, {int(best['trips'])} trips.")
    fewest = df.loc[df["stops_between"].idxmin()]
    shortest = df.loc[df["distance_km"].idxmin()]
    if fewest["route_name"] != best["route_name"]:
        text += f" Fewest stops: {fewest['route_name']} ({int(fewest['stops_between'])})."
    if shortest["route_name"] != best["route_name"]:
        text += f" Shortest distance: {shortest['route_name']} ({shortest['distance_km']} km)."
    text += " (Score is our own model, not an official PMPML rating.)"
    return text
