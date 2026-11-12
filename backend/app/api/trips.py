"""HTTP routes for trips. HTTP only — all logic lives in app.services."""

from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Path, status
from sqlmodel import Session

from app import config
from app.db import get_session
from app.schemas import TripComparisonRead, TripCreate, TripRead, TripUpdate
from app.services import comparison as comparison_service
from app.services import geo, weather
from app.services import trips as trip_service

router = APIRouter(prefix="/api/trips", tags=["trips"])


def get_geocoder() -> trip_service.Geocoder:
    """Dependency: the real Open-Meteo geocoder (overridden with a fake in tests)."""
    return geo.geocode


def get_weather_provider() -> comparison_service.WeatherProvider:
    """Dependency: the real Open-Meteo current weather (overridden with a fake in tests)."""
    return weather.current_weather


def get_now() -> datetime:
    """Dependency: current local time (overridden with a fixed time in tests)."""
    return datetime.now(ZoneInfo(config.LOCAL_TIMEZONE))


SessionDep = Annotated[Session, Depends(get_session)]
GeocoderDep = Annotated[trip_service.Geocoder, Depends(get_geocoder)]
WeatherDep = Annotated[comparison_service.WeatherProvider, Depends(get_weather_provider)]
NowDep = Annotated[datetime, Depends(get_now)]
TripId = Annotated[int, Path(ge=1, le=config.SQLITE_MAX_INTEGER)]


@router.get("", response_model=list[TripRead])
def list_trips(session: SessionDep):
    return trip_service.list_trips(session)


@router.post("", response_model=TripRead, status_code=status.HTTP_201_CREATED)
def create_trip(data: TripCreate, session: SessionDep, geocoder: GeocoderDep):
    return trip_service.create_trip(session, data, geocoder)


@router.get("/{trip_id}", response_model=TripRead)
def get_trip(trip_id: TripId, session: SessionDep):
    return trip_service.get_trip(session, trip_id)


@router.put("/{trip_id}", response_model=TripRead)
def update_trip(trip_id: TripId, data: TripUpdate, session: SessionDep, geocoder: GeocoderDep):
    return trip_service.update_trip(session, trip_id, data, geocoder)


@router.get("/{trip_id}/comparison", response_model=TripComparisonRead)
def compare_trip(trip_id: TripId, session: SessionDep, weather_provider: WeatherDep, now: NowDep):
    return comparison_service.compare_trip(session, trip_id, weather_provider, now)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(trip_id: TripId, session: SessionDep) -> None:
    trip_service.delete_trip(session, trip_id)
