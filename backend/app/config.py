"""Application configuration.

All constants live here, each with a source comment.
Values that differ between environments can be overridden with environment variables.
"""

import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import load_dotenv

# Source: project layout — backend/ is the parent of this app/ package.
BACKEND_DIR = Path(__file__).resolve().parent.parent

# Source: project decision — local secrets (Gemini key) live in backend/.env (gitignored, see
# backend/.env.example). Real environment variables take precedence over the file.
ENV_FILE = BACKEND_DIR / ".env"


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE lines from `path` into os.environ without overriding existing variables."""
    load_dotenv(path, override=False)


load_env_file(ENV_FILE)

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

# Source: Nominatim (OpenStreetMap) search API, no API key (https://nominatim.org/release-docs/latest/api/Search/).
# Fallback geocoder: used only when Open-Meteo finds nothing or is unavailable. Open-Meteo knows
# towns and districts ("Oliwa") but not addresses, POIs or "City District" ("Politechnika Gdańska").
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Source: Nominatim usage policy (https://operations.osmfoundation.org/policies/nominatim/):
# - a User-Agent identifying the application is required (library defaults are not accepted);
# - absolute maximum 1 request per second for the whole application;
# - repeated identical queries should be served from a cache;
# - the app must be able to switch the service off without a software update (env var below);
# - autocomplete use is forbidden; attribution "© OpenStreetMap contributors" must be shown in the UI.
NOMINATIM_USER_AGENT = "fast-travel/0.1 (commute comparison app)"
NOMINATIM_MIN_INTERVAL_SECONDS = 1.0
NOMINATIM_CACHE_SIZE = 256
NOMINATIM_ENABLED_ENV = "FAST_TRAVEL_NOMINATIM_ENABLED"  # "0" / "false" / "no" / "off" switches it off


def load_nominatim_enabled(environ: Mapping[str, str]) -> bool:
    """Nominatim fallback is on unless the env var says 0/false/no/off."""
    return environ.get(NOMINATIM_ENABLED_ENV, "").strip().lower() not in {"0", "false", "no", "off"}
# Source: project decision — the API usually answers in well under 1 s; fail fast instead of hanging the request.
GEOCODING_TIMEOUT_SECONDS = 5.0

# Source: Open-Meteo Forecast API, no API key needed (https://open-meteo.com/en/docs).
# `current` = conditions now; precipitation is the sum over the preceding 15-minute interval.
# Default units: temperature_2m in °C, precipitation in mm, wind_speed_10m in km/h.
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_CURRENT_VARIABLES = "temperature_2m,precipitation,wind_speed_10m"
# Source: project decision — same fail-fast limit as geocoding.
WEATHER_TIMEOUT_SECONDS = 5.0

# --- Recommendation: weather limits for walking / cycling ---------------------

# Source: WMO CIMO Guide (WMO-No. 8), ch. 6: amounts below 0.1 mm are a "trace";
# 0.1 mm is the smallest measurable precipitation. Applied to Open-Meteo's 15-min sum.
RAIN_THRESHOLD_MM = 0.1
# Source: Beaufort scale force 6 "strong breeze" starts at 39 km/h (22 kn)
# (Met Office, https://weather.metoffice.gov.uk/guides/coast-and-sea/beaufort-scale; MeteoSwiss table).
STRONG_WIND_THRESHOLD_KMH = 39.0
# Source: frost = air temperature below the freezing point of water, 0 °C (risk of ice on paths).
FROST_THRESHOLD_C = 0.0

# Source: acceptable one-way travel time by mode, Milakis & van Wee (2018, Delft vs Berkeley):
# walking 25-38.8 min, cycling 31.3-48.8 min (via saferoutespartnership.org, "Exploring
# acceptable travel time"). Mid-range values; slower walk/bike options are not recommended.
MAX_WALK_MINUTES = 30.0
MAX_BIKE_MINUTES = 40.0

ZERO_EMISSION_MAX_EXTRA_TIME_RATIO = 0.5

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

# Source: walking networks allow more direct routes than driving networks in almost all cities;
# network distance is at least ~14% longer than straight line (Boeing, "The Morphology and
# Circuity of Walkable and Drivable Street Networks", arXiv:1708.00836, 2019).
# 1.2 = between that 1.14 floor and the 1.3 used for roads (paths, crossings, cut-throughs).
WALK_DETOUR_FACTOR = 1.2
BIKE_DETOUR_FACTOR = 1.2

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

# --- Transport modes: fixed time per trip (minutes), added to driving/riding time ---

# Source: mean parking search time 3.57 min across six European studies (range 1.18-11.10)
# (hEART 2025 short paper 64, https://transp-or.epfl.ch/heart/2025/abstracts/hEART_2025_shortpaper_64.pdf).
# Rounded to 4 min. Walking from the parking spot is not included.
CAR_OVERHEAD_MINUTES = 4.0

# Source: average walking distance to a stop in Polish cities 390 m (Jakdojade data via auto-swiat.pl,
# "Auto czy autobus? Czy zbiorkom może zastąpić auto w każdej sytuacji?"), walked at both ends.
PUBLIC_TRANSPORT_STOP_DISTANCE_M = 390.0
# Source: ASSUMPTION — half-headway rule (Ansari Esfeh et al. 2021) with a 10-minute daytime
# headway; not measured for Gdańsk. Replace with local data when available.
PUBLIC_TRANSPORT_WAIT_MINUTES = 5.0
# Derived: walk to the stop + walk from the stop + wait = 2 x 390 m at WALK_SPEED_KMH + 5 = ~14.4 min.
PUBLIC_TRANSPORT_OVERHEAD_MINUTES = (
    2 * PUBLIC_TRANSPORT_STOP_DISTANCE_M / 1000 / WALK_SPEED_KMH * 60 + PUBLIC_TRANSPORT_WAIT_MINUTES
)

# Source: door to door — no parking search, no stop. (Locking a bike is under a minute; ignored.)
BIKE_OVERHEAD_MINUTES = 0.0
WALK_OVERHEAD_MINUTES = 0.0

# --- Car rush hour --------------------------------------------------------------

# Source: project decision (owner) — local time zone of the commutes.
LOCAL_TIMEZONE = "Europe/Warsaw"
# Source: project decision (owner) — morning and afternoon peaks, local time, [start, end).
CAR_PEAK_WINDOWS = (("07:30", "08:30"), ("15:00", "17:00"))
# Source: project decision (owner): +8-15 min in peak; the midpoint 11.5 is used because time
# must be deterministic (CLAUDE.md). Consistent with TomTom 2025 Gdańsk rush hour being slower
# (17.5 vs 25.6 km/h all-day -> ~+10 min on 10 km).
CAR_PEAK_PENALTY_MINUTES = 11.5

# Source: Natural Resources Canada idling model: 0.6 L/h per litre of engine displacement
# (https://www.nrcan.gc.ca/energy/efficiency/communities-infrastructure/transportation/idling/4457).
# ASSUMPTION: typical 1.5 L petrol engine -> 0.9 L/h (UK fleet guides quote 0.5-1 L/h for cars).
CAR_IDLE_FUEL_L_PER_HOUR = 0.6 * 1.5
# Source: UK DESNZ GHG conversion factors 2025, "Petrol (average biofuel blend)" = 2.06916 kg CO2e/litre.
PETROL_CO2_G_PER_LITRE = 2069.16
# Derived: the peak penalty minutes are spent idling in traffic ->
# 11.5 / 60 h x 0.9 L/h x 2069 g/L = ~357 g CO2e extra per car trip in rush hour.
CAR_PEAK_EXTRA_CO2_G = CAR_PEAK_PENALTY_MINUTES / 60 * CAR_IDLE_FUEL_L_PER_HOUR * PETROL_CO2_G_PER_LITRE

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

# --- AI trip parsing (POST /api/parse) ---

# Source: Gemini API generateContent endpoint (https://ai.google.dev/gemini-api/docs/structured-output).
GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Source: project decision (owner) — Gemini 3.1 Flash-Lite: cheap, fast, has a free tier
# (https://ai.google.dev/gemini-api/docs/gemini-3). Override with FAST_TRAVEL_GEMINI_MODEL.
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
# Source: project decision — extraction is a short answer; after this the rule-based parser is used.
LLM_TIMEOUT_SECONDS = 10.0
# Source: project decision — a trip description is one or two sentences; caps what is sent to the LLM.
PARSE_TEXT_MAX_LENGTH = 500

# Source: project decision — env var names, prefixed with the app name to avoid clashes.
DB_PATH_ENV = "FAST_TRAVEL_DB_PATH"
CORS_ORIGINS_ENV = "FAST_TRAVEL_CORS_ORIGINS"  # comma-separated list
GEMINI_API_KEY_ENV = "FAST_TRAVEL_GEMINI_API_KEY"  # empty or missing -> demo mode (rule-based parser)
GEMINI_MODEL_ENV = "FAST_TRAVEL_GEMINI_MODEL"


def load_db_path(environ: Mapping[str, str]) -> Path:
    """Return the SQLite file path from the environment, or the default."""
    raw = environ.get(DB_PATH_ENV, "").strip()
    return Path(raw) if raw else DEFAULT_DB_PATH


def load_cors_origins(environ: Mapping[str, str]) -> list[str]:
    """Return allowed CORS origins from a comma-separated env var, or the default."""
    raw = environ.get(CORS_ORIGINS_ENV, "")
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or list(DEFAULT_CORS_ORIGINS)


def load_gemini_api_key(environ: Mapping[str, str]) -> str | None:
    """Return the Gemini API key, or None (demo mode) when it is missing or blank."""
    return environ.get(GEMINI_API_KEY_ENV, "").strip() or None


def load_gemini_model(environ: Mapping[str, str]) -> str:
    """Return the Gemini model name from the environment, or the default."""
    return environ.get(GEMINI_MODEL_ENV, "").strip() or DEFAULT_GEMINI_MODEL


DB_PATH = load_db_path(os.environ)
DATABASE_URL = f"sqlite:///{DB_PATH}"
CORS_ORIGINS = load_cors_origins(os.environ)
NOMINATIM_ENABLED = load_nominatim_enabled(os.environ)
GEMINI_API_KEY = load_gemini_api_key(os.environ)
GEMINI_MODEL = load_gemini_model(os.environ)
