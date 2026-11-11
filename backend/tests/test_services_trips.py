from datetime import timedelta

import pytest

from app.models import Trip
from app.schemas import TripCreate, TripUpdate
from app.services import trips as svc


def _create(session, **overrides):
    data = {"name": "Work", "origin": "Kraków", "destination": "Wieliczka", **overrides}
    return svc.create_trip(session, TripCreate(**data))


def test_trip_not_found_error_message_and_id():
    err = svc.TripNotFoundError(7)
    assert err.trip_id == 7
    assert str(err) == "Trip 7 not found"


def test_create_trip_persists_and_returns_trip(session):
    trip = _create(session, notes="n", origin_lat=50.06, origin_lon=19.94)
    assert trip.id is not None
    assert trip.created_at is not None
    stored = session.get(Trip, trip.id)
    assert (stored.name, stored.notes, stored.origin_lat) == ("Work", "n", 50.06)


def test_list_trips_empty(session):
    assert svc.list_trips(session) == []


def test_list_trips_newest_first(session):
    older = _create(session, name="Old")
    newer = _create(session, name="New")
    older.created_at = newer.created_at - timedelta(hours=1)
    session.add(older)
    session.commit()

    assert [t.name for t in svc.list_trips(session)] == ["New", "Old"]


def test_list_trips_same_timestamp_newest_id_first(session):
    first = _create(session, name="A")
    second = _create(session, name="B")
    second.created_at = first.created_at
    session.add(second)
    session.commit()

    assert [t.name for t in svc.list_trips(session)] == ["B", "A"]


def test_get_trip_returns_trip(session):
    trip = _create(session)
    assert svc.get_trip(session, trip.id).id == trip.id


def test_get_trip_missing_raises(session):
    with pytest.raises(svc.TripNotFoundError):
        svc.get_trip(session, 999)


def test_update_trip_changes_only_sent_fields(session):
    trip = _create(session, notes="keep me")
    updated = svc.update_trip(session, trip.id, TripUpdate(name="Home"))
    assert updated.name == "Home"
    assert updated.origin == "Kraków"
    assert updated.notes == "keep me"


def test_update_trip_can_clear_optional_fields(session):
    trip = _create(session, notes="x", origin_lat=50.0, origin_lon=19.0)
    updated = svc.update_trip(session, trip.id, TripUpdate(notes=None, origin_lat=None, origin_lon=None))
    assert updated.notes is None
    assert updated.origin_lat is None and updated.origin_lon is None


def test_update_trip_does_not_touch_created_at(session):
    trip = _create(session)
    created_at = trip.created_at
    assert svc.update_trip(session, trip.id, TripUpdate(name="X")).created_at == created_at


def test_update_trip_missing_raises(session):
    with pytest.raises(svc.TripNotFoundError):
        svc.update_trip(session, 999, TripUpdate(name="X"))


def test_delete_trip_removes_it(session):
    trip = _create(session)
    svc.delete_trip(session, trip.id)
    assert session.get(Trip, trip.id) is None


def test_delete_trip_missing_raises(session):
    with pytest.raises(svc.TripNotFoundError):
        svc.delete_trip(session, 999)
