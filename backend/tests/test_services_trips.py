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


def test_place_coordinates_mapping():
    assert svc.PLACE_COORDINATES == {
        "origin": ("origin_lat", "origin_lon"),
        "destination": ("destination_lat", "destination_lon"),
    }


def test_update_trip_renamed_origin_clears_origin_coordinates_only(session):
    trip = _create(session, origin_lat=50.06, origin_lon=19.94, destination_lat=49.98, destination_lon=20.06)
    updated = svc.update_trip(session, trip.id, TripUpdate(origin="Tarnów"))
    assert updated.origin == "Tarnów"
    assert updated.origin_lat is None and updated.origin_lon is None
    assert (updated.destination_lat, updated.destination_lon) == (49.98, 20.06)


def test_update_trip_renamed_destination_clears_destination_coordinates(session):
    trip = _create(session, destination_lat=49.98, destination_lon=20.06)
    updated = svc.update_trip(session, trip.id, TripUpdate(destination="Bochnia"))
    assert updated.destination_lat is None and updated.destination_lon is None


def test_update_trip_rename_with_new_coordinates_keeps_them(session):
    trip = _create(session, origin_lat=50.06, origin_lon=19.94)
    updated = svc.update_trip(session, trip.id, TripUpdate(origin="Tarnów", origin_lat=50.01, origin_lon=20.99))
    assert (updated.origin_lat, updated.origin_lon) == (50.01, 20.99)


def test_update_trip_same_place_name_keeps_coordinates(session):
    trip = _create(session, origin_lat=50.06, origin_lon=19.94)
    updated = svc.update_trip(session, trip.id, TripUpdate(origin="Kraków"))
    assert (updated.origin_lat, updated.origin_lon) == (50.06, 19.94)


def test_update_trip_other_fields_keep_coordinates(session):
    trip = _create(session, origin_lat=50.06, origin_lon=19.94)
    updated = svc.update_trip(session, trip.id, TripUpdate(name="Home", notes="x"))
    assert (updated.origin_lat, updated.origin_lon) == (50.06, 19.94)


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
