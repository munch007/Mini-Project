"""Simple checks. Run:  python tests/test_core.py   (from the project folder)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from route_stats import haversine, overview_table
from scoring import to_score, add_convenience_score
from journey import hms_to_sec, sec_to_hm
from metro import load_metro, metro_options


def test_haversine_same_point_is_zero():
    assert haversine(18.5, 73.8, 18.5, 73.8) == 0


def test_haversine_known_distance():
    # about 111 km per degree of latitude
    assert 110 < haversine(18.0, 73.8, 19.0, 73.8) < 112


def test_time_conversion():
    assert hms_to_sec("08:30:00") == 30600
    assert hms_to_sec("25:00:00") == 90000
    assert sec_to_hm(30600) == "08:30"


def test_score_between_0_and_100():
    df = pd.DataFrame({"route_name": ["a", "b", "c"], "stops_between": [5, 10, 20],
                       "distance_km": [3.0, 6.0, 9.0], "trips": [40, 20, 5]})
    s = add_convenience_score(df)
    assert s["convenience_score"].between(0, 100).all()
    assert s.iloc[0]["route_name"] == "a"     # fewest stops, shortest, most trips


def test_equal_routes_score_100():
    assert (to_score(pd.Series([4, 4, 4]), higher_is_better=True) == 100).all()


def test_metro_same_line():
    m = load_metro(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "metro_stations.csv"))
    out = metro_options("Swargate", "Shivaji Nagar", m)
    assert out and "Purple" in out[0]["text"]


def test_overview_counts_one_direction_only():
    routes = pd.DataFrame({"route_id": ["1"], "route_short_name": ["1"], "route_long_name": ["A <-> B"]})
    trips = pd.DataFrame({"route_id": ["1", "1"], "trip_id": ["t0", "t1"], "direction_id": [0, 1]})
    rows = pd.DataFrame({"route_id": ["1"] * 5, "direction_id": [0, 0, 0, 1, 1],
                         "stop_sequence": [1, 2, 3, 1, 2], "cum_km": [0, 1, 2, 0, 1.5]})
    out = overview_table({"routes": routes, "trips": trips}, rows)
    assert out.iloc[0]["n_stops"] == 3          # not 5 (3 + 2)
    assert out.iloc[0]["length_km"] == 2


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("passed:", name)
