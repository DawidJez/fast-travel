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


# --- geocode_places ---

def test_geocode_places_both(geocoder):
    coords = svc.geocode_places({"origin": "Kraków", "destination": "Wieliczka"}, geocoder)
    assert coords == {
        "origin_lat": KRAKOW[0], "origin_lon": KRAKOW[1],
        "destination_lat": WIELICZKA[0], "destination_lon": WIELICZKA[1],
    }
    assert geocoder.calls == ["Kraków", "Wieliczka"]


def test_geocode_places_one(geocoder):
    assert svc.geocode_places({"destination": "Bochnia"}, geocoder) == {
        "destination_lat": BOCHNIA[0], "destination_lon": BOCHNIA[1],
    }


def test_geocode_places_empty_makes_no_calls(geocoder):
    assert svc.geocode_places({}, geocoder) == {}
    assert geocoder.calls == []


def test_geocode_places_propagates_errors(geocoder):
    with pytest.raises(PlaceNotFoundError):
        svc.geocode_places({"origin": "Atlantyda"}, geocoder)


# --- create ---

def test_create_trip_geocodes_both_places_and_persists(session, geocoder):
    trip = _create(session, geocoder, notes="n")
    assert trip.id is not None and trip.created_at is not None
    stored = session.get(Trip, trip.id)
    assert (stored.name, stored.notes) == ("Work", "n")
    assert _origin(stored) == KRAKOW and _destination(stored) == WIELICZKA
    assert geocoder.calls == ["Kraków", "Wieliczka"]


def test_create_trip_ignores_client_coordinates(session, geocoder):
    data = TripCreate(name="W", origin="Kraków", destination="Wieliczka", origin_lat=1.0, origin_lon=2.0)
    trip = svc.create_trip(session, data, geocoder)
    assert _origin(trip) == KRAKOW


def test_create_trip_unknown_place_saves_nothing(session, geocoder):
    with pytest.raises(PlaceNotFoundError, match="Atlantyda"):
        _create(session, geocoder, destination="Atlantyda")
    assert svc.list_trips(session) == []


def test_create_trip_geocoding_unavailable_saves_nothing(session, geocoder):
    geocoder.error = GeocodingUnavailableError("down")
    with pytest.raises(GeocodingUnavailableError):
        _create(session, geocoder)
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

def test_update_trip_changes_only_sent_fields_without_geocoding(session, geocoder):
    trip = _create(session, geocoder, notes="keep me")
    geocoder.calls.clear()
    updated = svc.update_trip(session, trip.id, TripUpdate(name="Home"), geocoder)
    assert updated.name == "Home"
    assert updated.origin == "Kraków"
    assert updated.notes == "keep me"
    assert geocoder.calls == []


def test_update_trip_renamed_origin_geocodes_origin_only(session, geocoder):
    trip = _create(session, geocoder)
    geocoder.calls.clear()
    updated = svc.update_trip(session, trip.id, TripUpdate(origin="Tarnów"), geocoder)
    assert updated.origin == "Tarnów"
    assert _origin(updated) == TARNOW
    assert _destination(updated) == WIELICZKA
    assert geocoder.calls == ["Tarnów"]


def test_update_trip_renamed_destination_geocodes_destination(session, geocoder):
    trip = _create(session, geocoder)
    updated = svc.update_trip(session, trip.id, TripUpdate(destination="Bochnia"), geocoder)
    assert _destination(updated) == BOCHNIA
    assert _origin(updated) == KRAKOW


def test_update_trip_both_renamed_geocodes_both(session, geocoder):
    trip = _create(session, geocoder)
    geocoder.calls.clear()
    updated = svc.update_trip(session, trip.id, TripUpdate(origin="Tarnów", destination="Bochnia"), geocoder)
    assert _origin(updated) == TARNOW and _destination(updated) == BOCHNIA
    assert geocoder.calls == ["Tarnów", "Bochnia"]


def test_update_trip_same_place_name_does_not_geocode(session, geocoder):
    trip = _create(session, geocoder)
    geocoder.calls.clear()
    updated = svc.update_trip(session, trip.id, TripUpdate(origin="Kraków", destination="Wieliczka"), geocoder)
    assert _origin(updated) == KRAKOW
    assert geocoder.calls == []


def test_update_trip_ignores_client_coordinates(session, geocoder):
    trip = _create(session, geocoder)
    updated = svc.update_trip(session, trip.id, TripUpdate(origin_lat=1.0, origin_lon=2.0), geocoder)
    assert _origin(updated) == KRAKOW


def test_update_trip_can_clear_notes(session, geocoder):
    trip = _create(session, geocoder, notes="x")
    assert svc.update_trip(session, trip.id, TripUpdate(notes=None), geocoder).notes is None


@pytest.mark.parametrize("error", [PlaceNotFoundError("Atlantyda"), GeocodingUnavailableError("down")])
def test_update_trip_geocoding_failure_saves_nothing(session, geocoder, error):
    trip = _create(session, geocoder)
    geocoder.error = error
    with pytest.raises(type(error)):
        svc.update_trip(session, trip.id, TripUpdate(name="New", origin="Tarnów"), geocoder)

    session.expire_all()  # read back from the database, not the identity map
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
