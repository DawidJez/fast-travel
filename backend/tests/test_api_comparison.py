"""GET /api/trips/{id}/comparison — fake geocoder, fake weather, fixed clock (see conftest)."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from app import config
from app.services.geo import GeocodingUnavailableError
from app.services.weather import Weather, WeatherUnavailableError

VALID = {"name": "Work", "origin": "Kraków", "destination": "Wieliczka"}


def _create(client, **overrides):
    return client.post("/api/trips", json={**VALID, **overrides}).json()["id"]


def _compare(client, trip_id):
    return client.get(f"/api/trips/{trip_id}/comparison")


# --- response shape ---

def test_comparison_returns_200_with_full_body(client):
    response = _compare(client, _create(client))
    assert response.status_code == 200
    body = response.json()

    assert set(body) == {
        "trip_id", "origin", "destination", "straight_line_km", "car_peak", "weather", "modes", "recommendation",
    }
    assert (body["origin"], body["destination"]) == ("Kraków", "Wieliczka")
    assert body["straight_line_km"] > 0
    assert body["car_peak"] is False
    assert body["weather"] == {"temperature_c": 12.0, "precipitation_mm": 0.0, "wind_speed_kmh": 10.0}
    assert [m["mode"] for m in body["modes"]] == ["walk", "bike", "car", "public_transport"]
    for row in body["modes"]:
        assert set(row) == {"mode", "distance_km", "time_minutes", "cost_pln", "co2_grams", "estimate", "note"}
        assert isinstance(row["co2_grams"], int)
    assert set(body["recommendation"]) == {"mode", "reason"}
    assert body["recommendation"]["mode"] in {"walk", "bike", "car", "public_transport"}


def test_comparison_known_values_for_cost_and_co2(client):
    body = _compare(client, _create(client)).json()
    rows = {m["mode"]: m for m in body["modes"]}
    assert rows["public_transport"]["cost_pln"] == config.PUBLIC_TRANSPORT_TICKET_PLN
    assert rows["walk"]["cost_pln"] == rows["bike"]["cost_pln"] == 0
    assert rows["walk"]["co2_grams"] == rows["bike"]["co2_grams"] == 0
    assert rows["car"]["cost_pln"] == pytest.approx(rows["car"]["distance_km"] * config.CAR_COST_PLN_PER_KM, abs=0.06)


def test_comparison_is_in_openapi_schema(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "get" in paths["/api/trips/{trip_id}/comparison"]


# --- clock / weather ---

def test_comparison_in_peak_marks_car_peak(client, clock):
    trip_id = _create(client)
    off_car = next(m for m in _compare(client, trip_id).json()["modes"] if m["mode"] == "car")
    clock.now = datetime(2026, 11, 12, 16, 0, tzinfo=ZoneInfo("Europe/Warsaw"))
    body = _compare(client, trip_id).json()
    peak_car = next(m for m in body["modes"] if m["mode"] == "car")

    assert body["car_peak"] is True
    assert peak_car["time_minutes"] == pytest.approx(off_car["time_minutes"] + 11.5, abs=0.1)


def test_comparison_rain_drops_walk_and_bike(client, weather_provider):
    weather_provider.weather = Weather(temperature_c=8, precipitation_mm=0.4, wind_speed_kmh=5)
    rec = _compare(client, _create(client)).json()["recommendation"]
    assert rec["mode"] in {"car", "public_transport"}
    assert "opady 0.4 mm" in rec["reason"]


def test_comparison_weather_unavailable_returns_200_without_weather(client, weather_provider):
    weather_provider.error = WeatherUnavailableError("down")
    response = _compare(client, _create(client))
    assert response.status_code == 200
    body = response.json()
    assert body["weather"] is None
    assert body["recommendation"]["reason"].startswith("Brak danych pogodowych")


# --- errors ---

def test_comparison_missing_trip_returns_404(client):
    response = _compare(client, 999)
    assert response.status_code == 404
    assert response.json() == {"detail": "Trip 999 not found"}


@pytest.mark.parametrize("bad_id", ["abc", "0", str(2**63)])
def test_comparison_invalid_id_returns_422(client, bad_id):
    assert _compare(client, bad_id).status_code == 422


def test_comparison_does_not_call_geocoder(client, geocoder):
    trip_id = _create(client)
    geocoder.calls.clear()
    assert _compare(client, trip_id).status_code == 200
    assert geocoder.calls == []


def test_comparison_works_while_geocoding_is_down(client, geocoder):
    trip_id = _create(client)
    geocoder.error = GeocodingUnavailableError("down")
    assert _compare(client, trip_id).status_code == 200


def test_comparison_does_not_change_the_trip(client):
    trip_id = _create(client)
    before = client.get(f"/api/trips/{trip_id}").json()
    _compare(client, trip_id)
    assert client.get(f"/api/trips/{trip_id}").json() == before


def test_comparison_public_transport_flagged_as_estimate(client):
    rows = {m["mode"]: m for m in _compare(client, _create(client)).json()["modes"]}
    assert rows["public_transport"]["estimate"] is True
    assert "bez rozkładów jazdy i kolei (np. SKM)" in rows["public_transport"]["note"]
    for mode in ("walk", "bike", "car"):
        assert (rows[mode]["estimate"], rows[mode]["note"]) == (False, None)


# --- dependencies ---

def test_get_weather_provider_returns_real_open_meteo_weather():
    from app.api.trips import get_weather_provider
    from app.services import weather

    assert get_weather_provider() is weather.current_weather


def test_get_now_is_aware_local_time():
    from app.api.trips import get_now

    now = get_now()
    assert now.tzinfo is not None
    assert str(now.tzinfo) == config.LOCAL_TIMEZONE
