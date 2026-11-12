"""HTTP routes for trips. HTTP only — all logic lives in app.services.trips."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlmodel import Session

from app import config
from app.db import get_session
from app.schemas import TripCreate, TripRead, TripUpdate
from app.services import geo
from app.services import trips as trip_service

router = APIRouter(prefix="/api/trips", tags=["trips"])


def get_geocoder() -> trip_service.Geocoder:
    """Dependency: the real Open-Meteo geocoder (overridden with a fake in tests)."""
    return geo.geocode


SessionDep = Annotated[Session, Depends(get_session)]
GeocoderDep = Annotated[trip_service.Geocoder, Depends(get_geocoder)]
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


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(trip_id: TripId, session: SessionDep) -> None:
    trip_service.delete_trip(session, trip_id)
