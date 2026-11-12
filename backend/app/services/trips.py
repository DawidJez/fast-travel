"""Trip CRUD logic. Routers call these functions and contain no logic of their own."""

from collections.abc import Callable

from sqlmodel import Session, col, select

from app.models import Trip
from app.schemas import TripCreate, TripUpdate
from app.services.geo import Coordinates, GeocodingError

# Place name -> coordinates; app.services.geo.geocode in production, a fake in tests.
Geocoder = Callable[[str], Coordinates]

# Which coordinate fields belong to which place name.
PLACE_COORDINATES = {
    "origin": ("origin_lat", "origin_lon"),
    "destination": ("destination_lat", "destination_lon"),
}


class TripNotFoundError(Exception):
    """Raised when a trip with the given id does not exist."""

    def __init__(self, trip_id: int):
        self.trip_id = trip_id
        super().__init__(f"Trip {trip_id} not found")


def fill_missing_coordinates(trip: Trip, geocoder: Geocoder) -> None:
    """Geocode every place of `trip` that has no coordinates yet (in place).

    Raises GeocodingError (place not found / service unavailable); the trip may be
    partially filled then, so callers must not commit it.
    """
    for place, (lat, lon) in PLACE_COORDINATES.items():
        if getattr(trip, lat) is None:
            point = geocoder(getattr(trip, place))
            setattr(trip, lat, point.lat)
            setattr(trip, lon, point.lon)


def create_trip(session: Session, data: TripCreate, geocoder: Geocoder) -> Trip:
    """Save a new trip; places sent without coordinates are geocoded first.

    Raises GeocodingError and saves nothing if a place cannot be geocoded.
    """
    trip = Trip(**data.model_dump())
    fill_missing_coordinates(trip, geocoder)
    session.add(trip)
    session.commit()
    session.refresh(trip)
    return trip


def list_trips(session: Session) -> list[Trip]:
    """All trips, newest first."""
    statement = select(Trip).order_by(col(Trip.created_at).desc(), col(Trip.id).desc())
    return list(session.exec(statement).all())


def get_trip(session: Session, trip_id: int) -> Trip:
    """Return one trip or raise TripNotFoundError."""
    trip = session.get(Trip, trip_id)
    if trip is None:
        raise TripNotFoundError(trip_id)
    return trip


def update_trip(session: Session, trip_id: int, data: TripUpdate, geocoder: Geocoder) -> Trip:
    """Apply only the fields that were sent; raise TripNotFoundError if missing.

    If a place name changes and no new coordinates for it are sent, its old
    coordinates are dropped and the new name is geocoded, so they never point at
    the previous place. Raises GeocodingError and leaves the stored trip unchanged
    if geocoding fails.
    """
    trip = get_trip(session, trip_id)
    changes = data.model_dump(exclude_unset=True)
    for place, (lat, lon) in PLACE_COORDINATES.items():
        renamed = place in changes and changes[place] != getattr(trip, place)
        if renamed and lat not in changes:
            changes[lat] = changes[lon] = None
    trip.sqlmodel_update(changes)
    try:
        fill_missing_coordinates(trip, geocoder)
    except GeocodingError:
        session.rollback()  # discard the in-memory edits; the stored row is untouched
        raise
    session.add(trip)
    session.commit()
    session.refresh(trip)
    return trip


def delete_trip(session: Session, trip_id: int) -> None:
    """Delete a trip; raise TripNotFoundError if missing."""
    trip = get_trip(session, trip_id)
    session.delete(trip)
    session.commit()
