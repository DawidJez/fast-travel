import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine
from sqlmodel.pool import StaticPool

from app import db
from app.api import trips as trips_api
from app.main import app
from app.services.geo import Coordinates, PlaceNotFoundError

# Coordinates the fake geocoder knows (rounded real values).
KNOWN_PLACES = {
    "Kraków": Coordinates(lat=50.0614, lon=19.9366),
    "Wieliczka": Coordinates(lat=49.9874, lon=20.0647),
    "Tarnów": Coordinates(lat=50.0121, lon=20.9858),
    "Bochnia": Coordinates(lat=49.9690, lon=20.4303),
    "Gdańsk": Coordinates(lat=54.3520, lon=18.6464),
}


class FakeGeocoder:
    """Stands in for app.services.geo.geocode: no network, records every call."""

    def __init__(self, places=None, error: Exception | None = None):
        self.places = KNOWN_PLACES if places is None else places
        self.error = error
        self.calls: list[str] = []

    def __call__(self, place: str) -> Coordinates:
        self.calls.append(place)
        if self.error is not None:
            raise self.error
        if place not in self.places:
            raise PlaceNotFoundError(place)
        return self.places[place]


@pytest.fixture
def geocoder():
    return FakeGeocoder()


@pytest.fixture
def make_geocoder():
    """Factory for a custom fake, e.g. make_geocoder(error=GeocodingUnavailableError("down"))."""
    return FakeGeocoder


@pytest.fixture
def empty_engine():
    """Fresh in-memory SQLite per test, without tables.

    StaticPool keeps one shared connection, so every session (and the TestClient's
    worker thread) sees the same in-memory database instead of a new empty one.
    """
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    yield engine
    engine.dispose()


@pytest.fixture
def engine(empty_engine):
    """Fresh in-memory SQLite per test, with all tables created."""
    db.create_db_and_tables(empty_engine)
    return empty_engine


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(engine, geocoder):
    """API client on the per-test in-memory DB and the fake geocoder (no real DB file, no network)."""

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[db.get_session] = override_get_session
    app.dependency_overrides[trips_api.get_geocoder] = lambda: geocoder
    yield TestClient(app)
    app.dependency_overrides.pop(db.get_session, None)
    app.dependency_overrides.pop(trips_api.get_geocoder, None)
