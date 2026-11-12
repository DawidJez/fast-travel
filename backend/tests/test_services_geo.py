"""Geocoding tests. All HTTP goes through httpx.MockTransport — no network access."""

import httpx
import pytest
from pydantic import ValidationError

from app import config
from app.services import geo

KRAKOW = {
    "results": [
        {"id": 3094802, "name": "Kraków", "latitude": 50.06143, "longitude": 19.93658, "country": "Polska"}
    ],
    "generationtime_ms": 0.17,
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

def test_geocode_returns_coordinates_of_first_result():
    assert geo.geocode("Kraków", _client(_json(KRAKOW))) == geo.Coordinates(lat=50.06143, lon=19.93658)


def test_geocode_takes_first_of_several_results():
    body = {"results": [{"latitude": 1.0, "longitude": 2.0}, {"latitude": 3.0, "longitude": 4.0}]}
    assert geo.geocode("X", _client(_json(body))) == geo.Coordinates(lat=1.0, lon=2.0)


def test_geocode_sends_expected_request():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=KRAKOW)

    geo.geocode("  Kraków ", _client(handler))

    (request,) = seen
    assert request.method == "GET"
    assert str(request.url).startswith(config.GEOCODING_URL)
    assert dict(request.url.params) == {
        "name": "Kraków", "count": "1", "language": "pl", "countryCode": "PL", "format": "json",
    }


def test_geocode_restricts_search_to_configured_country(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request.url.params["countryCode"])
        return httpx.Response(200, json=KRAKOW)

    monkeypatch.setattr(config, "GEOCODING_COUNTRY_CODE", "DE")
    geo.geocode("Berlin", _client(handler))
    assert seen == ["DE"]


def test_geocode_applies_timeout():
    seen = []

    def handler(request):
        seen.append(request.extensions["timeout"])
        return httpx.Response(200, json=KRAKOW)

    geo.geocode("Kraków", _client(handler))
    assert set(seen[0].values()) == {config.GEOCODING_TIMEOUT_SECONDS}


def test_geocode_without_client_uses_own_client(monkeypatch):
    transport = httpx.MockTransport(_json(KRAKOW))
    real_client = httpx.Client
    monkeypatch.setattr(geo.httpx, "Client", lambda: real_client(transport=transport))

    assert geo.geocode("Kraków").lat == 50.06143


# --- place not found ---

@pytest.mark.parametrize("body", [{"generationtime_ms": 0.08}, {"results": []}])
def test_geocode_no_results_raises_place_not_found(body):
    with pytest.raises(geo.PlaceNotFoundError, match="Xqzzy") as info:
        geo.geocode("Xqzzy", _client(_json(body)))
    assert info.value.place == "Xqzzy"


@pytest.mark.parametrize("place", ["", "   "])
def test_geocode_blank_name_raises_without_http_call(place):
    def handler(request):
        raise AssertionError("must not call the API")

    with pytest.raises(geo.PlaceNotFoundError):
        geo.geocode(place, _client(handler))


# --- service unavailable ---

def test_geocode_timeout_raises_unavailable():
    with pytest.raises(geo.GeocodingUnavailableError, match="did not answer within 5 s"):
        geo.geocode("Kraków", _client(_raise(httpx.ReadTimeout)))


def test_geocode_connect_timeout_raises_unavailable():
    with pytest.raises(geo.GeocodingUnavailableError, match="did not answer"):
        geo.geocode("Kraków", _client(_raise(httpx.ConnectTimeout)))


def test_geocode_connection_error_raises_unavailable():
    with pytest.raises(geo.GeocodingUnavailableError, match="unreachable"):
        geo.geocode("Kraków", _client(_raise(httpx.ConnectError)))


@pytest.mark.parametrize("status", [400, 429, 500, 503])
def test_geocode_http_error_status_raises_unavailable(status):
    body = {"error": True, "reason": "nope"}
    with pytest.raises(geo.GeocodingUnavailableError, match=f"HTTP {status}"):
        geo.geocode("Kraków", _client(_json(body, status)))


def test_geocode_invalid_json_raises_unavailable():
    handler = lambda request: httpx.Response(200, content=b"<html>oops</html>")  # noqa: E731
    with pytest.raises(geo.GeocodingUnavailableError, match="unexpected response"):
        geo.geocode("Kraków", _client(handler))


@pytest.mark.parametrize(
    "body",
    [
        {"results": [{"name": "Kraków"}]},                          # coordinates missing
        {"results": [{"latitude": 95.0, "longitude": 19.9}]},       # out of range
        {"results": [{"latitude": "north", "longitude": 19.9}]},    # wrong type
        {"results": "Kraków"},                                      # wrong container
        ["not", "an", "object"],
    ],
)
def test_geocode_unexpected_shape_raises_unavailable(body):
    with pytest.raises(geo.GeocodingUnavailableError, match="unexpected response"):
        geo.geocode("Kraków", _client(_json(body)))


def test_unavailable_and_not_found_share_base_class():
    assert issubclass(geo.PlaceNotFoundError, geo.GeocodingError)
    assert issubclass(geo.GeocodingUnavailableError, geo.GeocodingError)


# --- models ---

def test_coordinates_validates_ranges_and_is_frozen():
    point = geo.Coordinates(lat=50.0, lon=19.9)
    with pytest.raises(ValidationError):
        point.lat = 1.0
    with pytest.raises(ValidationError):
        geo.Coordinates(lat=91, lon=0)


def test_geo_response_defaults_to_no_results():
    assert geo._GeoResponse.model_validate({"generationtime_ms": 1}).results == []


def test_geo_result_ignores_extra_fields():
    result = geo._GeoResult.model_validate(KRAKOW["results"][0])
    assert (result.latitude, result.longitude) == (50.06143, 19.93658)
