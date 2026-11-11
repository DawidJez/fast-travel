"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
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


app.include_router(trips_api.router)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    """Liveness check: the app is up and answering requests."""
    return {"status": "ok"}
