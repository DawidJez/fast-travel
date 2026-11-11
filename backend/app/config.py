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
