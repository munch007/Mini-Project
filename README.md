# Pune CommuteWise

A dashboard that compares PMPML (Pune) bus routes by number of stops,
distance, trips and area coverage, with a simple convenience score.

## Problem
[2-3 lines: why is it hard to compare Pune bus routes?]

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
- data_loader.py: Sanchit Rauniyar
- route_stats.py: [member name]
- scoring.py: [member name]
- app.py: [member name]

## Team
- Sanchit Rauniyar
- Aadima Galande
- Sakshi Belbashe
- Sarthak Chavan

## Limitations
- Times are estimated
- Score is our own model, not an official PMPML rating
