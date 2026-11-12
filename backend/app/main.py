"""FastAPI application entry point."""

import math
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import config
from app import models  # noqa: F401  (registers tables before create_db_and_tables)
from app.api import trips as trips_api
from app.db import create_db_and_tables
from app.services.trips import TripNotFoundError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create database tables on startup."""
    create_db_and_tables()
    yield


app = FastAPI(title="Fast Travel", lifespan=lifespan)

# Allow the frontend origin(s) to call the API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(TripNotFoundError)
async def trip_not_found_handler(request: Request, exc: TripNotFoundError) -> JSONResponse:
    """Map a missing trip from the service layer to HTTP 404."""
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


def json_safe(value: Any) -> Any:
    """Replace NaN/Infinity (not valid JSON) with their string form, recursively."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Same 422 body as FastAPI's default, but safe when the rejected input contains NaN/Infinity."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": json_safe(jsonable_encoder(exc.errors()))},
    )


app.include_router(trips_api.router)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    """Liveness check: the app is up and answering requests."""
    return {"status": "ok"}
