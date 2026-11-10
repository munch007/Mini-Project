"""data_loader.py - loads the PMPML GTFS files into pandas tables."""
import os
import pandas as pd


def load_gtfs(folder="data"):
    """Read the 4 GTFS files we need from the given folder.

    Returns a dictionary of DataFrames: routes, trips, stops, stop_times.
    Raises a clear error if a file is missing.
    """
    files = {
        "routes": ["route_id", "route_short_name", "route_long_name"],
        "trips": ["route_id", "trip_id", "direction_id"],
        "stops": ["stop_id", "stop_name", "stop_lat", "stop_lon"],
        "stop_times": ["trip_id", "arrival_time", "stop_id", "stop_sequence"],
    }
    data = {}
    for name, columns in files.items():
        path = os.path.join(folder, name + ".txt")
        try:
            # usecols loads only the columns we need (saves memory)
            data[name] = pd.read_csv(path, usecols=columns, dtype={"route_id": str})
        except FileNotFoundError:
            raise FileNotFoundError(
                f"{path} not found. Unzip pmpml_gtfs_compat.zip into the '{folder}' folder."
            )
    return data


if __name__ == "__main__":
    d = load_gtfs()
    for name, table in d.items():
        print(name, table.shape)
