from datetime import timedelta

import pytest

from app.models import Trip
from app.schemas import TripCreate, TripUpdate
from app.services import trips as svc
from app.services.geo import GeocodingUnavailableError, PlaceNotFoundError

KRAKOW = (50.0614, 19.9366)
WIELICZKA = (49.9874, 20.0647)
TARNOW = (50.0121, 20.9858)
BOCHNIA = (49.9690, 20.4303)


def _create(session, geocoder, **overrides):
    data = {"name": "Work", "origin": "Kraków", "destination": "Wieliczka", **overrides}
    return svc.create_trip(session, TripCreate(**data), geocoder)


def _origin(trip):
    return (trip.origin_lat, trip.origin_lon)


def _destination(trip):
    return (trip.destination_lat, trip.destination_lon)


def test_trip_not_found_error_message_and_id():
    err = svc.TripNotFoundError(7)
    assert err.trip_id == 7
    assert str(err) == "Trip 7 not found"


def test_place_coordinates_mapping():
    assert svc.PLACE_COORDINATES == {
        "origin": ("origin_lat", "origin_lon"),
        "destination": ("destination_lat", "destination_lon"),
    }


# --- fill_missing_coordinates ---

def test_fill_missing_coordinates_geocodes_both_places(geocoder):
    trip = Trip(name="W", origin="Kraków", destination="Wieliczka")
    svc.fill_missing_coordinates(trip, geocoder)
    assert _origin(trip) == KRAKOW and _destination(trip) == WIELICZKA
    assert geocoder.calls == ["Kraków", "Wieliczka"]


def test_fill_missing_coordinates_keeps_existing_and_skips_geocoding(geocoder):
    trip = Trip(name="W", origin="Kraków", destination="Wieliczka", origin_lat=1.0, origin_lon=2.0)
    svc.fill_missing_coordinates(trip, geocoder)
    assert _origin(trip) == (1.0, 2.0)
    assert geocoder.calls == ["Wieliczka"]


def test_fill_missing_coordinates_nothing_missing_no_calls(geocoder):
    trip = Trip(name="W", origin="A", destination="B", origin_lat=1, origin_lon=2, destination_lat=3, destination_lon=4)
    svc.fill_missing_coordinates(trip, geocoder)
    assert geocoder.calls == []


def test_fill_missing_coordinates_propagates_errors(geocoder):
    with pytest.raises(PlaceNotFoundError):
        svc.fill_missing_coordinates(Trip(name="W", origin="Atlantyda", destination="Kraków"), geocoder)


# --- create ---

def test_create_trip_geocodes_and_persists(session, geocoder):
    trip = _create(session, geocoder, notes="n")
    assert trip.id is not None and trip.created_at is not None
    stored = session.get(Trip, trip.id)
    assert (stored.name, stored.notes) == ("Work", "n")
    assert _origin(stored) == KRAKOW and _destination(stored) == WIELICZKA


def test_create_trip_keeps_sent_coordinates(session, geocoder):
    trip = _create(session, geocoder, origin_lat=50.06, origin_lon=19.94)
    assert _origin(trip) == (50.06, 19.94)
    assert _destination(trip) == WIELICZKA
    assert geocoder.calls == ["Wieliczka"]


def test_create_trip_unknown_place_saves_nothing(session, geocoder):
    with pytest.raises(PlaceNotFoundError, match="Atlantyda"):
        _create(session, geocoder, destination="Atlantyda")
    assert svc.list_trips(session) == []


def test_create_trip_geocoding_unavailable_saves_nothing(session, make_geocoder):
    with pytest.raises(GeocodingUnavailableError):
        _create(session, make_geocoder(error=GeocodingUnavailableError("down")))
    assert svc.list_trips(session) == []


# --- list / get ---

def test_list_trips_empty(session):
    assert svc.list_trips(session) == []


def test_list_trips_newest_first(session, geocoder):
    older = _create(session, geocoder, name="Old")
    newer = _create(session, geocoder, name="New")
    older.created_at = newer.created_at - timedelta(hours=1)
    session.add(older)
    session.commit()

    assert [t.name for t in svc.list_trips(session)] == ["New", "Old"]


def test_list_trips_same_timestamp_newest_id_first(session, geocoder):
    first = _create(session, geocoder, name="A")
    second = _create(session, geocoder, name="B")
    second.created_at = first.created_at
    session.add(second)
    session.commit()

    assert [t.name for t in svc.list_trips(session)] == ["B", "A"]


def test_get_trip_returns_trip(session, geocoder):
    trip = _create(session, geocoder)
    assert svc.get_trip(session, trip.id).id == trip.id


def test_get_trip_missing_raises(session):
    with pytest.raises(svc.TripNotFoundError):
        svc.get_trip(session, 999)


# --- update ---

def test_update_trip_changes_only_sent_fields(session, geocoder):
    trip = _create(session, geocoder, notes="keep me")
    updated = svc.update_trip(session, trip.id, TripUpdate(name="Home"), geocoder)
    assert updated.name == "Home"
    assert updated.origin == "Kraków"
    assert updated.notes == "keep me"


def test_update_trip_renamed_origin_regeocodes_origin_only(session, geocoder):
    trip = _create(session, geocoder)
    geocoder.calls.clear()
    updated = svc.update_trip(session, trip.id, TripUpdate(origin="Tarnów"), geocoder)
    assert updated.origin == "Tarnów"
    assert _origin(updated) == TARNOW
    assert _destination(updated) == WIELICZKA
    assert geocoder.calls == ["Tarnów"]


def test_update_trip_renamed_destination_regeocodes_destination(session, geocoder):
    trip = _create(session, geocoder)
    updated = svc.update_trip(session, trip.id, TripUpdate(destination="Bochnia"), geocoder)
    assert _destination(updated) == BOCHNIA


def test_update_trip_rename_with_new_coordinates_keeps_them_without_geocoding(session, geocoder):
    trip = _create(session, geocoder)
    geocoder.calls.clear()
    updated = svc.update_trip(session, trip.id, TripUpdate(origin="Tarnów", origin_lat=50.01, origin_lon=20.99), geocoder)
    assert _origin(updated) == (50.01, 20.99)
    assert geocoder.calls == []


def test_update_trip_same_place_name_keeps_coordinates(session, geocoder):
    trip = _create(session, geocoder, origin_lat=50.06, origin_lon=19.94)
    geocoder.calls.clear()
    updated = svc.update_trip(session, trip.id, TripUpdate(origin="Kraków"), geocoder)
    assert _origin(updated) == (50.06, 19.94)
    assert geocoder.calls == []


def test_update_trip_other_fields_keep_coordinates(session, geocoder):
    trip = _create(session, geocoder, origin_lat=50.06, origin_lon=19.94)
    updated = svc.update_trip(session, trip.id, TripUpdate(name="Home", notes="x"), geocoder)
    assert _origin(updated) == (50.06, 19.94)


def test_update_trip_cleared_coordinates_are_geocoded_again(session, geocoder):
    trip = _create(session, geocoder, origin_lat=1.0, origin_lon=2.0)
    updated = svc.update_trip(session, trip.id, TripUpdate(origin_lat=None, origin_lon=None), geocoder)
    assert _origin(updated) == KRAKOW


def test_update_trip_can_clear_notes(session, geocoder):
    trip = _create(session, geocoder, notes="x")
    assert svc.update_trip(session, trip.id, TripUpdate(notes=None), geocoder).notes is None


def test_update_trip_geocoding_failure_leaves_stored_trip_unchanged(session, geocoder):
    trip = _create(session, geocoder)
    with pytest.raises(PlaceNotFoundError):
        svc.update_trip(session, trip.id, TripUpdate(name="New", origin="Atlantyda"), geocoder)

    stored = svc.get_trip(session, trip.id)
    assert (stored.name, stored.origin) == ("Work", "Kraków")
    assert _origin(stored) == KRAKOW


def test_update_trip_does_not_touch_created_at(session, geocoder):
    trip = _create(session, geocoder)
    created_at = trip.created_at
    assert svc.update_trip(session, trip.id, TripUpdate(name="X"), geocoder).created_at == created_at


def test_update_trip_missing_raises(session, geocoder):
    with pytest.raises(svc.TripNotFoundError):
        svc.update_trip(session, 999, TripUpdate(name="X"), geocoder)


# --- delete ---

def test_delete_trip_removes_it(session, geocoder):
    trip = _create(session, geocoder)
    svc.delete_trip(session, trip.id)
    assert session.get(Trip, trip.id) is None


def test_delete_trip_missing_raises(session):
    with pytest.raises(svc.TripNotFoundError):
        svc.delete_trip(session, 999)
