"""Application configuration.

All constants live here, each with a source comment.
Values that differ between environments can be overridden with environment variables.
"""

import os
from collections.abc import Mapping
from pathlib import Path

# Source: project layout — backend/ is the parent of this app/ package.
BACKEND_DIR = Path(__file__).resolve().parent.parent

# Source: project decision — SQLite file next to the backend (*.db is gitignored).
DEFAULT_DB_PATH = BACKEND_DIR / "fast_travel.db"

# Source: Vite dev server default origin (https://vite.dev/config/server-options#server-port).
DEFAULT_CORS_ORIGINS = ["http://localhost:5173"]

# Source: project decision — limits for trip text fields (form-friendly, keep DB rows small).
TRIP_NAME_MAX_LENGTH = 100
TRIP_PLACE_MAX_LENGTH = 200  # origin / destination
TRIP_NOTES_MAX_LENGTH = 1000

# Source: WGS 84 coordinate ranges (degrees), as used by Open-Meteo geocoding.
LATITUDE_MIN, LATITUDE_MAX = -90.0, 90.0
LONGITUDE_MIN, LONGITUDE_MAX = -180.0, 180.0

# Source: Open-Meteo Geocoding API, no API key needed (https://open-meteo.com/en/docs/geocoding-api).
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
# Source: project decision — Polish UI, Polish place names; one best match is enough for a form.
GEOCODING_LANGUAGE = "pl"
# Source: project decision — commutes are within Poland. Without this filter Open-Meteo returns
# "Sopot" in Romania/Serbia/Bulgaria first (Polish Sopot not even in the top 5, checked 2026-11-12).
# ISO 3166-1 alpha-2 code, sent as the API's `countryCode` parameter.
GEOCODING_COUNTRY_CODE = "PL"
# Source: project decision — the API usually answers in well under 1 s; fail fast instead of hanging the request.
GEOCODING_TIMEOUT_SECONDS = 5.0

# Source: Open-Meteo Forecast API, no API key needed (https://open-meteo.com/en/docs).
# `current` = conditions now; precipitation is the sum over the preceding 15-minute interval.
# Default units: temperature_2m in °C, precipitation in mm, wind_speed_10m in km/h.
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_CURRENT_VARIABLES = "temperature_2m,precipitation,wind_speed_10m"
# Source: project decision — same fail-fast limit as geocoding.
WEATHER_TIMEOUT_SECONDS = 5.0

# --- Distance ---------------------------------------------------------------

# Source: IUGG mean Earth radius R1 = 6371.0088 km (Moritz, "Geodetic Reference System 1980",
# Journal of Geodesy 74, 2000). Standard value for haversine on a spherical Earth.
EARTH_RADIUS_KM = 6371.0088

# Source: road circuity (network distance / straight-line distance). Typical values 1.1-1.5
# (review: Boeing, arXiv:2409.08016); median 1.25 for European road connections
# (Heinold & Makowski, Networks and Spatial Economics, 2026, doi:10.1007/s11067-026-09729-y);
# national factors in Ballou, Rahardja & Sakai, Transportation Research A 36(9), 2002.
# Rounded up to 1.3 (project spec) because urban commutes are more circuitous than intercity links.
DETOUR_FACTOR = 1.3

# --- Transport modes: speed (km/h), door-to-door averages --------------------

# Source: TomTom Traffic Index 2025, Gdańsk: 23 min 26 s per 10 km in the Polish city ranking
# (auto-swiat.pl, "Łódź i Lublin w światowej czołówce...", 2026) -> 10 / (23.43 / 60) = 25.6 km/h.
# The TomTom city page (https://www.tomtom.com/traffic-index/city/gdansk/) also shows
# 34 min 17 s / 17.5 km/h, most likely rush hour. Parking search time is not included.
CAR_SPEED_KMH = 25.6

# Source: Puls Gdańska tram ranking 2023, Gdańsk average commercial tram speed 17.7 km/h
# (stops included; via antyweb.pl/tramwaje-w-polsce-2023). Walking to the stop and waiting
# are not included, so real door-to-door public transport is slower.
PUBLIC_TRANSPORT_SPEED_KMH = 17.7

# Source: Copenhagen Bicycle Account (City of Copenhagen), average cycling speed 15.5-16.4 km/h
# in 2006-2016; GPS door-to-door studies give 13.5-14.5 km/h. 15 km/h sits between them.
BIKE_SPEED_KMH = 15.0

# Source: Bohannon, "Comfortable and maximum walking speed of adults aged 20-79 years",
# Age and Ageing 26(1), 1997: mean comfortable speed 1.27-1.46 m/s (4.6-5.3 km/h).
WALK_SPEED_KMH = 5.0

# --- Transport modes: cost (PLN) ---------------------------------------------

# Source: Rozporządzenie Ministra Infrastruktury z 22.12.2022 (Dz.U. 2023 poz. 5), in force
# since 17.01.2023: 1.15 PLN/km for a passenger car with engine > 900 cm3 ("kilometrówka").
# Full cost of use (fuel, wear, insurance), not fuel only.
CAR_COST_PLN_PER_KM = 1.15

# Source: ZTM Gdańsk, 75-minute normal ticket 6.00 PLN, price list valid from 3.04.2023
# (https://ztm.gda.pl/bilety/bilety-jednorazowe,a,3019). Flat fare per one-way trip;
# ZTM Gdańsk has no 60-minute ticket, the 75-minute one is the closest.
PUBLIC_TRANSPORT_TICKET_PLN = 6.00

# Source: no fuel or fare for own bike / walking.
BIKE_COST_PLN_PER_KM = 0.0
WALK_COST_PLN_PER_KM = 0.0

# --- Transport modes: CO2 (g CO2e per passenger-km, direct / tank-to-wheel) --

# Source: UK DESNZ GHG conversion factors 2025, "Average car, unknown fuel" = 0.16725 kg CO2e/km
# (https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2025).
# Per vehicle-km, i.e. assumes the driver travels alone (typical commute).
CAR_CO2_G_PER_KM = 167.0

# Source: UK DESNZ GHG conversion factors 2025, "Average local bus" = 0.10385 kg CO2e/passenger-km.
# Used for all public transport: UK tram factor (0.0286) reflects the UK grid; on the coal-heavy
# Polish grid tram emissions are roughly 3x higher, i.e. close to the bus value.
PUBLIC_TRANSPORT_CO2_G_PER_KM = 104.0

# Source: no direct emissions (DESNZ / DfT journey emissions guidance: cycling and walking = 0).
BIKE_CO2_G_PER_KM = 0.0
WALK_CO2_G_PER_KM = 0.0

# Source: SQLite INTEGER is a signed 64-bit value (https://www.sqlite.org/datatype3.html);
# larger ids cannot exist and would crash the driver, so the API rejects them up front.
SQLITE_MAX_INTEGER = 2**63 - 1

# Source: project decision — env var names, prefixed with the app name to avoid clashes.
DB_PATH_ENV = "FAST_TRAVEL_DB_PATH"
CORS_ORIGINS_ENV = "FAST_TRAVEL_CORS_ORIGINS"  # comma-separated list


def load_db_path(environ: Mapping[str, str]) -> Path:
    """Return the SQLite file path from the environment, or the default."""
    raw = environ.get(DB_PATH_ENV, "").strip()
    return Path(raw) if raw else DEFAULT_DB_PATH


def load_cors_origins(environ: Mapping[str, str]) -> list[str]:
    """Return allowed CORS origins from a comma-separated env var, or the default."""
    raw = environ.get(CORS_ORIGINS_ENV, "")
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or list(DEFAULT_CORS_ORIGINS)


DB_PATH = load_db_path(os.environ)
DATABASE_URL = f"sqlite:///{DB_PATH}"
CORS_ORIGINS = load_cors_origins(os.environ)
