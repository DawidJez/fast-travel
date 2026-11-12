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
# Source: project decision — the API usually answers in well under 1 s; fail fast instead of hanging the request.
GEOCODING_TIMEOUT_SECONDS = 5.0

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
