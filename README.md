# Pune CommuteWise

A dashboard that compares PMPML (Pune) bus routes by number of stops,
distance, trips and area coverage, with a simple convenience score.

## Problem Statement

Pune has hundreds of PMPML bus routes, but there is no simple way for a
student or daily commuter to compare the routes that connect two areas.
Existing apps mainly help find a bus or plan a journey. They do not show,
side by side, how many stops a route has between two places, how far it
travels, or how often it runs. Because of this, commuters often pick a
route by habit or guesswork, and may choose a slower or less frequent bus.

## Who Faces This Problem
College students and daily commuters in Pune who depend on public
transport.

## Why It Is Important
Better route choices save travel time and make public transport easier to
use, which supports sustainable cities (SDG 11) and Digital India (using
open public data).

## Existing Solutions and Gap
- croyla/pmpml-gtfs: provides open PMPML data, but has no analysis or
  user interface.
- Google Maps / PMPML and Chartr apps: help plan journeys, but do not
  explain a route comparison through stops, distance and trips.
- Gap: no simple tool lets a user compare routes between two areas and
  see why one is more convenient.

## Our Solution
Pune CommuteWise is a Python-based dashboard that:
- finds all routes that serve two chosen areas
- calculates stops between them, distance and number of trips
- gives each route a convenience score (our own model)
- shows the result in charts and a plain-language recommendation

## Objectives
1. Load and clean open PMPML GTFS data using Python (pandas).
2. Calculate route statistics such as stops, distance and trips.
3. Build a transparent, rule-based convenience score.
4. Present the results in an easy Streamlit dashboard for students.

## Role of Python
Data loading, cleaning, distance calculation (haversine formula),
route matching, scoring and the dashboard are all written in Python.

## Features
- Route overview (total routes, stops, longest route)
- Route explorer
- Compare 2-3 routes with charts
- Convenience score and recommendation

## Data Source
PMPML GTFS data from github.com/croyla/pmpml-gtfs (MIT-0 license).
Travel times in the data are estimates, not official schedules.

## How to Run
1. Install Python
2. pip install -r requirements.txt
3. streamlit run app.py

## Project Structure
'''mini-project/
├── README.md              # Project overview, problem, how to run
├── requirements.txt       # Libraries: pandas, plotly, streamlit
├── app.py                 # Streamlit dashboard (Member 4)
├── data_loader.py         # Loads GTFS files with pandas (Member 1)
├── route_stats.py         # Distance, route stats, route matching (Member 2)
├── scoring.py             # Convenience score and recommendation (Member 3)
└── data/
    ├── routes.txt         # Route names and IDs
    ├── trips.txt          # Trips on each route
    ├── stops.txt          # Stop names and coordinates
    └── stop_times.txt     # Order of stops on each trip'''
## Team
- Sanchit Rauniyar
- Aadima Galande
- Sakshi Belbashe
- Sarthak Chavan

## Limitations
- Times are estimated
- Score is our own model, not an official PMPML rating
