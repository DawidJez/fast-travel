"""Trip CRUD logic. Routers call these functions and contain no logic of their own."""

from sqlmodel import Session, col, select

from app.models import Trip
from app.schemas import TripCreate, TripUpdate


class TripNotFoundError(Exception):
    """Raised when a trip with the given id does not exist."""

    def __init__(self, trip_id: int):
        self.trip_id = trip_id
        super().__init__(f"Trip {trip_id} not found")


def create_trip(session: Session, data: TripCreate) -> Trip:
    """Save a new trip and return it with id and created_at filled in."""
    trip = Trip(**data.model_dump())
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


def update_trip(session: Session, trip_id: int, data: TripUpdate) -> Trip:
    """Apply only the fields that were sent; raise TripNotFoundError if missing."""
    trip = get_trip(session, trip_id)
    trip.sqlmodel_update(data.model_dump(exclude_unset=True))
    session.add(trip)
    session.commit()
    session.refresh(trip)
    return trip


def delete_trip(session: Session, trip_id: int) -> None:
    """Delete a trip; raise TripNotFoundError if missing."""
    trip = get_trip(session, trip_id)
    session.delete(trip)
    session.commit()
