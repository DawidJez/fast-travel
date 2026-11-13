"""Weather tests. All HTTP goes through httpx.MockTransport — no network access."""

import httpx
import pytest
from pydantic import ValidationError

from app import config
from app.services import weather
from app.services.geo import Coordinates

GDANSK = Coordinates(lat=54.35227, lon=18.64912)

# Trimmed real response (2026-11-12, Gdańsk).
RESPONSE = {
    "latitude": 54.355087,
    "longitude": 18.63427,
    "timezone": "Europe/Warsaw",
    "current_units": {"time": "iso8601", "interval": "seconds", "temperature_2m": "°C",
                      "precipitation": "mm", "wind_speed_10m": "km/h"},
    "current": {"time": "2026-11-12T19:00", "interval": 900,
                "temperature_2m": 3.8, "precipitation": 0.0, "wind_speed_10m": 10.0},
}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _json(body, status=200):
    return lambda request: httpx.Response(status, json=body)


def _raise(exc_type):
    def handler(request):
        raise exc_type("boom", request=request)

    return handler


# --- success ---

def test_current_weather_maps_fields():
    assert weather.current_weather(GDANSK, _client(_json(RESPONSE))) == weather.Weather(
        temperature_c=3.8, precipitation_mm=0.0, wind_speed_kmh=10.0
    )


def test_current_weather_rain_and_frost():
    body = {"current": {"temperature_2m": -2.5, "precipitation": 1.2, "wind_speed_10m": 35.0}}
    result = weather.current_weather(GDANSK, _client(_json(body)))
    assert (result.temperature_c, result.precipitation_mm, result.wind_speed_kmh) == (-2.5, 1.2, 35.0)


def test_current_weather_sends_expected_request():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=RESPONSE)

    weather.current_weather(GDANSK, _client(handler))

    (request,) = seen
    assert request.method == "GET"
    assert str(request.url).startswith(config.WEATHER_URL)
    assert dict(request.url.params) == {
        "latitude": "54.35227",
        "longitude": "18.64912",
        "current": "temperature_2m,precipitation,wind_speed_10m",
        "timezone": "auto",
    }


def test_current_weather_applies_timeout():
    seen = []

    def handler(request):
        seen.append(request.extensions["timeout"])
        return httpx.Response(200, json=RESPONSE)

    weather.current_weather(GDANSK, _client(handler))
    assert set(seen[0].values()) == {config.WEATHER_TIMEOUT_SECONDS}


def test_current_weather_without_client_uses_own_client(monkeypatch):
    transport = httpx.MockTransport(_json(RESPONSE))
    real_client = httpx.Client
    monkeypatch.setattr(weather.httpx, "Client", lambda: real_client(transport=transport))

    assert weather.current_weather(GDANSK).temperature_c == 3.8


# --- service unavailable ---

@pytest.mark.parametrize("exc", [httpx.ReadTimeout, httpx.ConnectTimeout])
def test_current_weather_timeout_raises_unavailable(exc):
    with pytest.raises(weather.WeatherUnavailableError, match="did not answer within 5 s"):
        weather.current_weather(GDANSK, _client(_raise(exc)))


def test_current_weather_connection_error_raises_unavailable():
    with pytest.raises(weather.WeatherUnavailableError, match="unreachable"):
        weather.current_weather(GDANSK, _client(_raise(httpx.ConnectError)))


@pytest.mark.parametrize("status", [400, 429, 500, 503])
def test_current_weather_http_error_raises_unavailable(status):
    body = {"error": True, "reason": "nope"}
    with pytest.raises(weather.WeatherUnavailableError, match=f"HTTP {status}"):
        weather.current_weather(GDANSK, _client(_json(body, status)))


def test_current_weather_invalid_json_raises_unavailable():
    handler = lambda request: httpx.Response(200, content=b"<html>oops</html>")  # noqa: E731
    with pytest.raises(weather.WeatherUnavailableError, match="unexpected response"):
        weather.current_weather(GDANSK, _client(handler))


@pytest.mark.parametrize(
    "body",
    [
        {"latitude": 54.3},                                                             # no "current"
        {"current": {"temperature_2m": 3.8, "precipitation": 0.0}},                     # wind missing
        {"current": {"temperature_2m": "warm", "precipitation": 0, "wind_speed_10m": 1}},
        {"current": {"temperature_2m": 3.8, "precipitation": -1, "wind_speed_10m": 1}},  # negative rain
        {"current": {"temperature_2m": 3.8, "precipitation": 0, "wind_speed_10m": -5}},  # negative wind
        {"current": {"temperature_2m": None, "precipitation": 0, "wind_speed_10m": 1}},  # null value
    ],
)
def test_current_weather_unexpected_shape_raises_unavailable(body):
    with pytest.raises(weather.WeatherUnavailableError, match="unexpected response"):
        weather.current_weather(GDANSK, _client(_json(body)))


@pytest.mark.parametrize(
    "field", ["temperature_2m", "precipitation", "wind_speed_10m"],
)
@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
def test_current_weather_non_finite_values_raise_unavailable(field, bad):
    values = {"temperature_2m": "3.8", "precipitation": "0.0", "wind_speed_10m": "10.0", field: bad}
    raw = '{"current": {%s}}' % ", ".join(f'"{k}": {v}' for k, v in values.items())
    handler = lambda request: httpx.Response(200, content=raw.encode())  # noqa: E731
    with pytest.raises(weather.WeatherUnavailableError, match="unexpected response"):
        weather.current_weather(GDANSK, _client(handler))


def test_weather_model_rejects_nan():
    with pytest.raises(ValidationError):
        weather.Weather(temperature_c=float("nan"), precipitation_mm=0, wind_speed_kmh=0)


# --- model ---

def test_weather_is_frozen_and_validated():
    w = weather.Weather(temperature_c=1, precipitation_mm=0, wind_speed_kmh=0)
    with pytest.raises(ValidationError):
        w.temperature_c = 2
    with pytest.raises(ValidationError):
        weather.Weather(temperature_c=1, precipitation_mm=-0.1, wind_speed_kmh=0)
