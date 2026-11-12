from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlmodel import Session

from app import config
from app.models import Trip
from app.schemas import TripCreate, TripRead, TripUpdate

VALID = {"name": "Work", "origin": "Kraków", "destination": "Wieliczka"}


# --- TripCreate ---

def test_create_minimal_valid():
    trip = TripCreate(**VALID)
    assert trip.name == "Work"
    assert trip.notes is None


def test_create_strips_whitespace():
    trip = TripCreate(name="  Work ", origin=" Kraków", destination="Wieliczka  ")
    assert (trip.name, trip.origin, trip.destination) == ("Work", "Kraków", "Wieliczka")


@pytest.mark.parametrize("field", ["name", "origin", "destination"])
def test_create_requires_field(field):
    data = {k: v for k, v in VALID.items() if k != field}
    with pytest.raises(ValidationError):
        TripCreate(**data)


@pytest.mark.parametrize("field", ["name", "origin", "destination"])
def test_create_rejects_blank(field):
    with pytest.raises(ValidationError):
        TripCreate(**{**VALID, field: "   "})


@pytest.mark.parametrize(
    ("field", "limit"),
    [
        ("name", config.TRIP_NAME_MAX_LENGTH),
        ("origin", config.TRIP_PLACE_MAX_LENGTH),
        ("destination", config.TRIP_PLACE_MAX_LENGTH),
        ("notes", config.TRIP_NOTES_MAX_LENGTH),
    ],
)
def test_create_max_lengths(field, limit):
    TripCreate(**{**VALID, field: "x" * limit})
    with pytest.raises(ValidationError):
        TripCreate(**{**VALID, field: "x" * (limit + 1)})


def test_create_notes_stripped_and_blank_becomes_none():
    assert TripCreate(**VALID, notes="  via A4  ").notes == "via A4"
    assert TripCreate(**VALID, notes="   ").notes is None


def test_create_ignores_client_coordinates():
    trip = TripCreate(**VALID, origin_lat=1.0, origin_lon=2.0, destination_lat=3.0, destination_lon=4.0)
    assert set(trip.model_dump()) == {"name", "origin", "destination", "notes"}


def test_create_ignores_server_fields():
    trip = TripCreate(**VALID, id=99, created_at="2020-01-01T00:00:00Z")
    assert "id" not in trip.model_dump()
    assert "created_at" not in trip.model_dump()


# --- TripUpdate ---

def test_update_empty_is_valid_and_sets_nothing():
    assert TripUpdate().model_dump(exclude_unset=True) == {}


def test_update_partial_only_sent_fields():
    update = TripUpdate(name=" Home ", origin="Tarnów")
    assert update.model_dump(exclude_unset=True) == {"name": "Home", "origin": "Tarnów"}


def test_update_ignores_client_coordinates():
    update = TripUpdate(name="Home", origin_lat=1.0, origin_lon=2.0)
    assert update.model_dump(exclude_unset=True) == {"name": "Home"}


@pytest.mark.parametrize("field", ["name", "origin", "destination"])
def test_update_rejects_null_required_field(field):
    with pytest.raises(ValidationError):
        TripUpdate(**{field: None})


@pytest.mark.parametrize("field", ["name", "origin", "destination"])
def test_update_rejects_blank_required_field(field):
    with pytest.raises(ValidationError):
        TripUpdate(**{field: "  "})


def test_update_allows_clearing_notes():
    assert TripUpdate(notes=None).model_dump(exclude_unset=True) == {"notes": None}


# --- TripRead ---

def test_read_from_db_object_has_utc_created_at(engine):
    with Session(engine) as session:
        trip = Trip(**VALID, notes="n", origin_lat=50.06, origin_lon=19.94, destination_lat=49.99, destination_lon=20.06)
        session.add(trip)
        session.commit()
        session.refresh(trip)
        read = TripRead.model_validate(trip)

    assert read.id == trip.id
    assert read.name == "Work"
    assert read.origin_lat == 50.06
    assert read.destination_lat == 49.99
    assert read.created_at.tzinfo is not None
    assert read.created_at.utcoffset().total_seconds() == 0


def test_read_assume_utc_keeps_aware_datetime():
    aware = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert TripRead.assume_utc(aware) is aware


def test_read_assume_utc_marks_naive_as_utc():
    naive = datetime(2026, 1, 1, 12, 0)
    assert TripRead.assume_utc(naive) == datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
