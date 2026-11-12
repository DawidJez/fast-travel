from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app import config
from app.models import Trip
from app.schemas import TripComparisonRead
from app.services import calculators as calc
from app.services.calculators import Mode
from app.services.comparison import compare_trip, ensure_coordinates
from app.services.distance import haversine_km
from app.services.geo import Coordinates, GeocodingUnavailableError, PlaceNotFoundError
from app.services.trips import TripNotFoundError
from app.services.weather import Weather, WeatherUnavailableError

WARSAW = ZoneInfo("Europe/Warsaw")
NOON = datetime(2026, 11, 12, 12, 0, tzinfo=WARSAW)
MORNING_PEAK = datetime(2026, 11, 12, 8, 0, tzinfo=WARSAW)

KRAKOW = Coordinates(lat=50.0614, lon=19.9366)
WIELICZKA = Coordinates(lat=49.9874, lon=20.0647)


def _trip(session, **fields):
    data = {
        "name": "Work", "origin": "Kraków", "destination": "Wieliczka",
        "origin_lat": KRAKOW.lat, "origin_lon": KRAKOW.lon,
        "destination_lat": WIELICZKA.lat, "destination_lon": WIELICZKA.lon,
        **fields,
    }
    trip = Trip(**data)
    session.add(trip)
    session.commit()
    session.refresh(trip)
    return trip


def _mode(result: TripComparisonRead, mode: Mode):
    return next(m for m in result.modes if m.mode is mode)


# --- happy path ---

def test_compare_trip_builds_full_comparison(session, geocoder, weather_provider):
    trip = _trip(session)
    result = compare_trip(session, trip.id, geocoder, weather_provider, NOON)

    straight = haversine_km(KRAKOW, WIELICZKA)
    assert result.trip_id == trip.id
    assert (result.origin, result.destination) == ("Kraków", "Wieliczka")
    assert result.straight_line_km == round(straight, 1)
    assert result.car_peak is False
    assert [m.mode for m in result.modes] == list(Mode)
    assert result.weather.model_dump() == {"temperature_c": 12.0, "precipitation_mm": 0.0, "wind_speed_kmh": 10.0}
    assert geocoder.calls == []  # coordinates already stored

    for row in result.modes:
        km = calc.route_distance_km(row.mode, straight)
        assert row.distance_km == round(km, 1)
        assert row.time_minutes == round(calc.travel_time_minutes(row.mode, km), 1)
        assert row.cost_pln == round(calc.cost_pln(row.mode, km), 2)
        assert row.co2_grams == round(calc.co2_grams(row.mode, km))


def test_compare_trip_uses_mode_specific_detour(session, geocoder, weather_provider):
    result = compare_trip(session, _trip(session).id, geocoder, weather_provider, NOON)
    assert _mode(result, Mode.BIKE).distance_km < _mode(result, Mode.CAR).distance_km


def test_compare_trip_rounding(session, geocoder, weather_provider):
    result = compare_trip(session, _trip(session).id, geocoder, weather_provider, NOON)
    for row in result.modes:
        assert row.distance_km == round(row.distance_km, 1)
        assert row.time_minutes == round(row.time_minutes, 1)
        assert row.cost_pln == round(row.cost_pln, 2)
        assert isinstance(row.co2_grams, int)


def test_compare_trip_recommendation_long_trip_good_weather(session, geocoder, weather_provider):
    # Kraków - Wieliczka is ~12 km straight line: walk/bike exceed the time limits, car is fastest.
    result = compare_trip(session, _trip(session).id, geocoder, weather_provider, NOON)
    assert result.recommendation.mode is Mode.CAR
    assert "rower odpada" in result.recommendation.reason


def test_compare_trip_recommendation_short_trip_good_weather(session, geocoder, weather_provider):
    # ~1 km straight line: bike is fastest.
    nearby = Coordinates(lat=KRAKOW.lat + 0.009, lon=KRAKOW.lon)
    trip = _trip(session, destination="Blisko", destination_lat=nearby.lat, destination_lon=nearby.lon)
    result = compare_trip(session, trip.id, geocoder, weather_provider, NOON)
    assert result.recommendation.mode is Mode.BIKE
    assert result.recommendation.reason.startswith("Najszybciej: rower")


def test_compare_trip_asks_weather_for_origin(session, geocoder, weather_provider):
    compare_trip(session, _trip(session).id, geocoder, weather_provider, NOON)
    assert weather_provider.calls == [KRAKOW]


# --- rush hour ---

def test_compare_trip_in_peak_adds_car_time_and_co2(session, geocoder, weather_provider):
    trip = _trip(session)
    off = compare_trip(session, trip.id, geocoder, weather_provider, NOON)
    peak = compare_trip(session, trip.id, geocoder, weather_provider, MORNING_PEAK)

    assert (off.car_peak, peak.car_peak) == (False, True)
    car_off, car_peak = _mode(off, Mode.CAR), _mode(peak, Mode.CAR)
    assert car_peak.time_minutes == pytest.approx(car_off.time_minutes + config.CAR_PEAK_PENALTY_MINUTES, abs=0.1)
    assert car_peak.co2_grams == pytest.approx(car_off.co2_grams + config.CAR_PEAK_EXTRA_CO2_G, abs=1)
    assert _mode(peak, Mode.BIKE) == _mode(off, Mode.BIKE)


# --- weather ---

def test_compare_trip_rain_drops_walk_and_bike(session, geocoder, weather_provider):
    weather_provider.weather = Weather(temperature_c=10, precipitation_mm=1.0, wind_speed_kmh=5)
    result = compare_trip(session, _trip(session).id, geocoder, weather_provider, NOON)
    assert result.recommendation.mode not in (Mode.WALK, Mode.BIKE)
    assert "opady 1 mm" in result.recommendation.reason


def test_compare_trip_weather_unavailable_still_returns_comparison(session, geocoder, weather_provider):
    weather_provider.error = WeatherUnavailableError("down")
    result = compare_trip(session, _trip(session).id, geocoder, weather_provider, NOON)
    assert result.weather is None
    assert len(result.modes) == 4
    assert result.recommendation.reason.startswith("Brak danych pogodowych")


def test_compare_trip_other_weather_errors_are_not_swallowed(session, geocoder, weather_provider):
    weather_provider.error = RuntimeError("bug")
    with pytest.raises(RuntimeError):
        compare_trip(session, _trip(session).id, geocoder, weather_provider, NOON)


# --- errors / coordinates ---

def test_compare_trip_missing_trip_raises(session, geocoder, weather_provider):
    with pytest.raises(TripNotFoundError):
        compare_trip(session, 999, geocoder, weather_provider, NOON)


def test_compare_trip_geocodes_and_saves_missing_coordinates(session, geocoder, weather_provider):
    trip = _trip(session, origin_lat=None, origin_lon=None, destination_lat=None, destination_lon=None)
    result = compare_trip(session, trip.id, geocoder, weather_provider, NOON)

    assert geocoder.calls == ["Kraków", "Wieliczka"]
    assert result.straight_line_km == round(haversine_km(KRAKOW, WIELICZKA), 1)
    stored = session.get(Trip, trip.id)
    assert (stored.origin_lat, stored.destination_lon) == (KRAKOW.lat, WIELICZKA.lon)


def test_compare_trip_geocoding_failure_raises_and_keeps_trip(session, geocoder, weather_provider):
    trip = _trip(session, origin="Atlantyda", origin_lat=None, origin_lon=None)
    with pytest.raises(PlaceNotFoundError):
        compare_trip(session, trip.id, geocoder, weather_provider, NOON)
    stored = session.get(Trip, trip.id)
    assert stored.origin_lat is None
    assert weather_provider.calls == []


def test_compare_trip_same_origin_and_destination_is_all_zero(session, geocoder, weather_provider):
    trip = _trip(session, destination="Kraków", destination_lat=KRAKOW.lat, destination_lon=KRAKOW.lon)
    result = compare_trip(session, trip.id, geocoder, weather_provider, NOON)
    assert result.straight_line_km == 0
    assert all(m.time_minutes == m.cost_pln == m.co2_grams == 0 for m in result.modes)


# --- ensure_coordinates ---

def test_ensure_coordinates_noop_when_complete(session, geocoder):
    trip = _trip(session)
    ensure_coordinates(session, trip, geocoder)
    assert geocoder.calls == []


def test_ensure_coordinates_fills_only_missing_place(session, geocoder):
    trip = _trip(session, destination_lat=None, destination_lon=None)
    ensure_coordinates(session, trip, geocoder)
    assert geocoder.calls == ["Wieliczka"]
    assert session.get(Trip, trip.id).destination_lat == WIELICZKA.lat


def test_ensure_coordinates_unavailable_rolls_back(session, make_geocoder):
    trip = _trip(session, origin_lat=None, origin_lon=None)
    with pytest.raises(GeocodingUnavailableError):
        ensure_coordinates(session, trip, make_geocoder(error=GeocodingUnavailableError("down")))
    assert session.get(Trip, trip.id).origin_lat is None
