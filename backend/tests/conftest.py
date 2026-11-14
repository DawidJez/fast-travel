from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine
from sqlmodel.pool import StaticPool

from app import db
from app.api import parse as parse_api
from app.api import trips as trips_api
from app.main import app
from app.services.geo import Coordinates, PlaceNotFoundError
from app.services.parsing import DemoClient, ParsedTrip
from app.services.weather import Weather

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


class FakeWeather:
    """Stands in for app.services.weather.current_weather: fixed weather or an error."""

    def __init__(self, weather: Weather | None = None, error: Exception | None = None):
        self.weather = weather or Weather(temperature_c=12.0, precipitation_mm=0.0, wind_speed_kmh=10.0)
        self.error = error
        self.calls: list[Coordinates] = []

    def __call__(self, point: Coordinates) -> Weather:
        self.calls.append(point)
        if self.error is not None:
            raise self.error
        return self.weather


# Off-peak by default: Thursday 12:00 in Warsaw.
DEFAULT_NOW = datetime(2026, 11, 12, 12, 0, tzinfo=ZoneInfo("Europe/Warsaw"))


@pytest.fixture
def geocoder():
    """The single geocoder mock: knows KNOWN_PLACES; set `.error = ...` to simulate a failure."""
    return FakeGeocoder()


@pytest.fixture
def weather_provider():
    return FakeWeather()


class FakeLLM:
    """Stands in for GeminiClient: returns a fixed ParsedTrip (or raises), records every call."""

    source = "ai"

    def __init__(self, answer: ParsedTrip | None = None, error: Exception | None = None):
        self.answer = answer or ParsedTrip()
        self.error = error
        self.calls: list[str] = []

    def parse_trip(self, text: str) -> ParsedTrip:
        self.calls.append(text)
        if self.error is not None:
            raise self.error
        return self.answer


@pytest.fixture
def llm():
    """Holder for the LLM client the API sees: `llm.client = FakeLLM(...)`. DemoClient by default,
    so tests never call the real Gemini API even when backend/.env has a key."""

    class Holder:
        client = DemoClient()

    return Holder()


@pytest.fixture
def clock():
    """Mutable holder for the time the API sees: set clock.now = ... in a test."""

    class Clock:
        now = DEFAULT_NOW

    return Clock()


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
def client(engine, geocoder, weather_provider, clock, llm):
    """API client on the per-test in-memory DB, fake geocoder, fake weather and a fixed clock
    (no real DB file, no network, deterministic time)."""

    def override_get_session():
        with Session(engine) as session:
            yield session

    overrides = {
        db.get_session: override_get_session,
        trips_api.get_geocoder: lambda: geocoder,
        trips_api.get_weather_provider: lambda: weather_provider,
        trips_api.get_now: lambda: clock.now,
        parse_api.get_llm_client: lambda: llm.client,
    }
    app.dependency_overrides.update(overrides)
    yield TestClient(app)
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)
