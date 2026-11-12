"""Trip CRUD logic. Routers call these functions and contain no logic of their own.

Coordinates are set only by the server: geocoded on create, and on update only for
a place whose name changed. Geocoding runs before anything is changed, so a failure
(GeocodingError) leaves the database untouched.
"""

from collections.abc import Callable

from sqlmodel import Session, col, select

from app.models import Trip
from app.schemas import TripCreate, TripUpdate
from app.services.geo import Coordinates

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


def geocode_places(places: dict[str, str], geocoder: Geocoder) -> dict[str, float]:
    """Geocode {"origin": name, ...} into {"origin_lat": .., "origin_lon": .., ...}.

    Raises GeocodingError (place not found / service unavailable) on the first failure.
    """
    coordinates: dict[str, float] = {}
    for place, name in places.items():
        lat, lon = PLACE_COORDINATES[place]
        point = geocoder(name)
        coordinates[lat] = point.lat
        coordinates[lon] = point.lon
    return coordinates


def create_trip(session: Session, data: TripCreate, geocoder: Geocoder) -> Trip:
    """Geocode origin and destination, then save the trip.

    Raises GeocodingError and saves nothing if a place cannot be geocoded.
    """
    fields = data.model_dump()
    coordinates = geocode_places({place: fields[place] for place in PLACE_COORDINATES}, geocoder)
    trip = Trip(**fields, **coordinates)
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

    A place whose name changed is geocoded again; an unchanged name keeps its
    coordinates without calling the geocoder. Raises GeocodingError and leaves the
    stored trip unchanged if geocoding fails.
    """
    trip = get_trip(session, trip_id)
    changes = data.model_dump(exclude_unset=True)
    renamed = {
        place: changes[place]
        for place in PLACE_COORDINATES
        if place in changes and changes[place] != getattr(trip, place)
    }
    changes.update(geocode_places(renamed, geocoder))  # may raise before anything is modified
    trip.sqlmodel_update(changes)
    session.add(trip)
    session.commit()
    session.refresh(trip)
    return trip


def delete_trip(session: Session, trip_id: int) -> None:
    """Delete a trip; raise TripNotFoundError if missing."""
    trip = get_trip(session, trip_id)
    session.delete(trip)
    session.commit()
