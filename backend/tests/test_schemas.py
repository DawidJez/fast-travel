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
    assert trip.origin_lat is None


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


def test_create_accepts_coordinates_at_bounds():
    trip = TripCreate(**VALID, origin_lat=-90, origin_lon=180, destination_lat=90, destination_lon=-180)
    assert (trip.origin_lat, trip.origin_lon) == (-90, 180)


@pytest.mark.parametrize(
    ("field", "value"),
    [("origin_lat", 90.1), ("destination_lat", -90.1), ("origin_lon", 180.1), ("destination_lon", -180.1)],
)
def test_create_rejects_out_of_range_coordinates(field, value):
    partner = {"origin_lat": "origin_lon", "origin_lon": "origin_lat",
               "destination_lat": "destination_lon", "destination_lon": "destination_lat"}[field]
    with pytest.raises(ValidationError):
        TripCreate(**VALID, **{field: value, partner: 0})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("schema", [TripCreate, TripUpdate])
def test_rejects_non_finite_coordinates(schema, value):
    base = VALID if schema is TripCreate else {}
    with pytest.raises(ValidationError, match="finite number"):
        schema(**base, origin_lat=value, origin_lon=0)


@pytest.mark.parametrize("field", ["origin_lat", "origin_lon", "destination_lat", "destination_lon"])
def test_create_rejects_half_coordinate_pair(field):
    with pytest.raises(ValidationError, match="must be given together"):
        TripCreate(**VALID, **{field: 10.0})


def test_create_accepts_one_full_pair_only():
    trip = TripCreate(**VALID, origin_lat=50.06, origin_lon=19.94)
    assert trip.destination_lat is None and trip.destination_lon is None


def test_create_ignores_server_fields():
    trip = TripCreate(**VALID, id=99, created_at="2020-01-01T00:00:00Z")
    assert "id" not in trip.model_dump()
    assert "created_at" not in trip.model_dump()


# --- TripUpdate ---

def test_update_empty_is_valid_and_sets_nothing():
    assert TripUpdate().model_dump(exclude_unset=True) == {}


def test_update_partial_only_sent_fields():
    update = TripUpdate(name=" Home ", origin_lat=50.06, origin_lon=19.94)
    assert update.model_dump(exclude_unset=True) == {"name": "Home", "origin_lat": 50.06, "origin_lon": 19.94}


@pytest.mark.parametrize("field", ["origin_lat", "origin_lon", "destination_lat", "destination_lon"])
def test_update_rejects_half_coordinate_pair(field):
    with pytest.raises(ValidationError, match="must be (given|sent) together"):
        TripUpdate(**{field: 10.0})


@pytest.mark.parametrize("field", ["origin_lat", "destination_lon"])
def test_update_rejects_clearing_half_coordinate_pair(field):
    with pytest.raises(ValidationError, match="must be sent together"):
        TripUpdate(**{field: None})


def test_update_rejects_pair_with_one_null():
    with pytest.raises(ValidationError, match="must be given together"):
        TripUpdate(origin_lat=50.06, origin_lon=None)


@pytest.mark.parametrize("field", ["name", "origin", "destination"])
def test_update_rejects_null_required_field(field):
    with pytest.raises(ValidationError):
        TripUpdate(**{field: None})


@pytest.mark.parametrize("field", ["name", "origin", "destination"])
def test_update_rejects_blank_required_field(field):
    with pytest.raises(ValidationError):
        TripUpdate(**{field: "  "})


def test_update_allows_clearing_optional_fields():
    update = TripUpdate(notes=None, origin_lat=None, origin_lon=None)
    assert update.model_dump(exclude_unset=True) == {"notes": None, "origin_lat": None, "origin_lon": None}


def test_update_rejects_out_of_range_coordinates():
    with pytest.raises(ValidationError):
        TripUpdate(destination_lat=0, destination_lon=200)


# --- TripRead ---

def test_read_from_db_object_has_utc_created_at(engine):
    with Session(engine) as session:
        trip = Trip(**VALID, notes="n", origin_lat=50.06, origin_lon=19.94)
        session.add(trip)
        session.commit()
        session.refresh(trip)
        read = TripRead.model_validate(trip)

    assert read.id == trip.id
    assert read.name == "Work"
    assert read.origin_lat == 50.06
    assert read.destination_lat is None
    assert read.created_at.tzinfo is not None
    assert read.created_at.utcoffset().total_seconds() == 0


def test_read_assume_utc_keeps_aware_datetime():
    aware = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert TripRead.assume_utc(aware) is aware


def test_read_assume_utc_marks_naive_as_utc():
    naive = datetime(2026, 1, 1, 12, 0)
    assert TripRead.assume_utc(naive) == datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
