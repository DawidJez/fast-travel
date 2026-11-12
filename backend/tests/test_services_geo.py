"""Geocoding tests. All HTTP goes through httpx.MockTransport — no network access."""

import httpx
import pytest
from pydantic import ValidationError

from app import config
from app.services import geo

OPEN_METEO_HOST = "geocoding-api.open-meteo.com"
NOMINATIM_HOST = "nominatim.openstreetmap.org"

KRAKOW = {
    "results": [
        {"id": 3094802, "name": "Kraków", "latitude": 50.06143, "longitude": 19.93658, "country": "Polska"}
    ],
    "generationtime_ms": 0.17,
}
OPEN_METEO_EMPTY = {"generationtime_ms": 0.08}
# Trimmed real Nominatim answer (2026-11-12): lat/lon are strings.
POLITECHNIKA = [
    {"lat": "54.3718684", "lon": "18.6166793", "importance": 0.52,
     "display_name": "Politechnika Gdańska, Gdańsk, województwo pomorskie, Polska"}
]


@pytest.fixture(autouse=True)
def fresh_nominatim(monkeypatch):
    """No cache between tests, no real waiting, fallback enabled."""
    geo.clear_nominatim_cache()
    monkeypatch.setattr(geo, "_nominatim_last_request", float("-inf"))
    monkeypatch.setattr(config, "NOMINATIM_MIN_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(config, "NOMINATIM_ENABLED", True)
    yield
    geo.clear_nominatim_cache()


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _json(body, status=200):
    return lambda request: httpx.Response(status, json=body)


def _raise(exc_type):
    def handler(request):
        raise exc_type("boom", request=request)

    return handler


def _route(open_meteo, nominatim, seen=None):
    """Dispatch by host; record (host, request) in `seen`."""

    def handler(request):
        if seen is not None:
            seen.append((request.url.host, request))
        if request.url.host == OPEN_METEO_HOST:
            return open_meteo(request)
        if request.url.host == NOMINATIM_HOST:
            return nominatim(request)
        raise AssertionError(f"unexpected host {request.url.host}")

    return handler


def _never(request):
    raise AssertionError("this service must not be called")


# =========================== Open-Meteo ======================================

def test_open_meteo_returns_first_result():
    assert geo.geocode_open_meteo("Kraków", _client(_json(KRAKOW))) == geo.Coordinates(lat=50.06143, lon=19.93658)


def test_open_meteo_takes_first_of_several_results():
    body = {"results": [{"latitude": 1.0, "longitude": 2.0}, {"latitude": 3.0, "longitude": 4.0}]}
    assert geo.geocode_open_meteo("X", _client(_json(body))) == geo.Coordinates(lat=1.0, lon=2.0)


def test_open_meteo_sends_expected_request():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=KRAKOW)

    geo.geocode_open_meteo("Kraków", _client(handler))

    (request,) = seen
    assert request.method == "GET"
    assert str(request.url).startswith(config.GEOCODING_URL)
    assert dict(request.url.params) == {
        "name": "Kraków", "count": "1", "language": "pl", "countryCode": "PL", "format": "json",
    }
    assert set(request.extensions["timeout"].values()) == {config.GEOCODING_TIMEOUT_SECONDS}


def test_open_meteo_restricts_search_to_configured_country(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request.url.params["countryCode"])
        return httpx.Response(200, json=KRAKOW)

    monkeypatch.setattr(config, "GEOCODING_COUNTRY_CODE", "DE")
    geo.geocode_open_meteo("Berlin", _client(handler))
    assert seen == ["DE"]


@pytest.mark.parametrize("body", [OPEN_METEO_EMPTY, {"results": []}])
def test_open_meteo_no_results_raises_place_not_found(body):
    with pytest.raises(geo.PlaceNotFoundError, match="Xqzzy") as info:
        geo.geocode_open_meteo("Xqzzy", _client(_json(body)))
    assert info.value.place == "Xqzzy"


@pytest.mark.parametrize(
    ("handler", "message"),
    [
        (_raise(httpx.ReadTimeout), "Geocoding service did not answer within 5 s"),
        (_raise(httpx.ConnectTimeout), "did not answer"),
        (_raise(httpx.ConnectError), "Geocoding service is unreachable"),
        (_json({"error": True}, 500), "Geocoding service returned HTTP 500"),
        (_json({"error": True}, 429), "HTTP 429"),
        (lambda request: httpx.Response(200, content=b"<html>oops</html>"), "unexpected response"),
    ],
)
def test_open_meteo_failures_raise_unavailable(handler, message):
    with pytest.raises(geo.GeocodingUnavailableError, match=message):
        geo.geocode_open_meteo("Kraków", _client(handler))


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
def test_open_meteo_unexpected_shape_raises_unavailable(body):
    with pytest.raises(geo.GeocodingUnavailableError, match="unexpected response"):
        geo.geocode_open_meteo("Kraków", _client(_json(body)))


# =========================== Nominatim =======================================

def test_nominatim_parses_string_coordinates():
    assert geo.geocode_nominatim("Politechnika Gdańska", _client(_json(POLITECHNIKA))) == geo.Coordinates(
        lat=54.3718684, lon=18.6166793
    )


def test_nominatim_sends_policy_compliant_request():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=POLITECHNIKA)

    geo.geocode_nominatim("Politechnika Gdańska", _client(handler))

    (request,) = seen
    assert str(request.url).startswith(config.NOMINATIM_URL)
    assert dict(request.url.params) == {
        "q": "Politechnika Gdańska", "format": "jsonv2", "limit": "1", "countrycodes": "pl", "accept-language": "pl",
    }
    assert request.headers["User-Agent"] == config.NOMINATIM_USER_AGENT
    assert not request.headers["User-Agent"].startswith("python-httpx")  # library default is not allowed
    assert set(request.extensions["timeout"].values()) == {config.GEOCODING_TIMEOUT_SECONDS}


def test_nominatim_empty_list_raises_place_not_found():
    with pytest.raises(geo.PlaceNotFoundError):
        geo.geocode_nominatim("Xqzzy", _client(_json([])))


@pytest.mark.parametrize(
    ("handler", "message"),
    [
        (_raise(httpx.ReadTimeout), "Nominatim did not answer within 5 s"),
        (_raise(httpx.ConnectError), "Nominatim is unreachable"),
        (_json({"error": "x"}, 403), "Nominatim returned HTTP 403"),
        (lambda request: httpx.Response(200, content=b"<html/>"), "unexpected response"),
        (_json({"lat": "1", "lon": "2"}), "unexpected response"),        # object instead of list
        (_json([{"lat": "north", "lon": "2"}]), "unexpected response"),
        (_json([{"lat": "95", "lon": "2"}]), "unexpected response"),       # out of range
    ],
)
def test_nominatim_failures_raise_unavailable(handler, message):
    with pytest.raises(geo.GeocodingUnavailableError, match=message):
        geo.geocode_nominatim("Politechnika Gdańska", _client(handler))


def test_nominatim_caches_hits_case_insensitively():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=POLITECHNIKA)

    client = _client(handler)
    first = geo.geocode_nominatim("Politechnika Gdańska", client)
    second = geo.geocode_nominatim("politechnika gdańska", client)
    assert first == second
    assert len(calls) == 1


def test_nominatim_caches_not_found():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=[])

    client = _client(handler)
    for _ in range(2):
        with pytest.raises(geo.PlaceNotFoundError):
            geo.geocode_nominatim("Xqzzy", client)
    assert len(calls) == 1


def test_nominatim_does_not_cache_errors():
    responses = iter([httpx.Response(503), httpx.Response(200, json=POLITECHNIKA)])
    client = _client(lambda request: next(responses))
    with pytest.raises(geo.GeocodingUnavailableError):
        geo.geocode_nominatim("Politechnika Gdańska", client)
    assert geo.geocode_nominatim("Politechnika Gdańska", client).lat == 54.3718684


def test_nominatim_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(config, "NOMINATIM_CACHE_SIZE", 2)
    client = _client(_json(POLITECHNIKA))
    for name in ("a", "b", "c"):
        geo.geocode_nominatim(name, client)
    assert list(geo._nominatim_cache) == ["b", "c"]


def test_nominatim_throttle_waits_between_requests(monkeypatch):
    clock = {"now": 100.0}
    sleeps = []
    monkeypatch.setattr(geo.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(geo.time, "sleep", lambda s: (sleeps.append(s), clock.update(now=clock["now"] + s)))
    monkeypatch.setattr(config, "NOMINATIM_MIN_INTERVAL_SECONDS", 1.0)

    client = _client(_json(POLITECHNIKA))
    geo.geocode_nominatim("a", client)       # first request: no wait
    clock["now"] += 0.3
    geo.geocode_nominatim("b", client)       # 0.3 s later: waits the remaining 0.7 s
    clock["now"] += 5
    geo.geocode_nominatim("c", client)       # long after: no wait
    geo.geocode_nominatim("a", client)       # cached: no request, no wait
    assert sleeps == [pytest.approx(0.7)]


# =========================== combined geocode() ==============================

def test_geocode_uses_open_meteo_when_it_finds_the_place():
    seen = []
    result = geo.geocode("Kraków", _client(_route(_json(KRAKOW), _never, seen)))
    assert result == geo.Coordinates(lat=50.06143, lon=19.93658)
    assert [host for host, _ in seen] == [OPEN_METEO_HOST]


def test_geocode_falls_back_to_nominatim_when_open_meteo_finds_nothing():
    seen = []
    result = geo.geocode("Politechnika Gdańska", _client(_route(_json(OPEN_METEO_EMPTY), _json(POLITECHNIKA), seen)))
    assert result == geo.Coordinates(lat=54.3718684, lon=18.6166793)
    assert [host for host, _ in seen] == [OPEN_METEO_HOST, NOMINATIM_HOST]


def test_geocode_falls_back_to_nominatim_when_open_meteo_is_down():
    result = geo.geocode("Kraków", _client(_route(_raise(httpx.ConnectError), _json(POLITECHNIKA))))
    assert result.lat == 54.3718684


def test_geocode_not_found_anywhere_raises_place_not_found():
    with pytest.raises(geo.PlaceNotFoundError, match="Xqzzy"):
        geo.geocode("Xqzzy", _client(_route(_json(OPEN_METEO_EMPTY), _json([]))))


@pytest.mark.parametrize(
    ("open_meteo", "nominatim"),
    [
        (_json(OPEN_METEO_EMPTY), _json({}, 503)),          # not found + down -> can't be sure
        (_raise(httpx.ReadTimeout), _json([])),              # down + not found
        (_raise(httpx.ReadTimeout), _raise(httpx.ReadTimeout)),
    ],
)
def test_geocode_unavailable_when_no_hit_and_a_service_failed(open_meteo, nominatim):
    with pytest.raises(geo.GeocodingUnavailableError):
        geo.geocode("Kraków", _client(_route(open_meteo, nominatim)))


def test_geocode_reports_first_failure_message():
    with pytest.raises(geo.GeocodingUnavailableError, match="Geocoding service did not answer"):
        geo.geocode("Kraków", _client(_route(_raise(httpx.ReadTimeout), _raise(httpx.ConnectError))))


def test_geocode_nominatim_switched_off_never_calls_it(monkeypatch):
    monkeypatch.setattr(config, "NOMINATIM_ENABLED", False)
    with pytest.raises(geo.PlaceNotFoundError):
        geo.geocode("Politechnika Gdańska", _client(_route(_json(OPEN_METEO_EMPTY), _never)))


def test_geocode_strips_name_before_calling_services():
    seen = []
    geo.geocode("  Kraków ", _client(_route(_json(KRAKOW), _never, seen)))
    assert seen[0][1].url.params["name"] == "Kraków"


@pytest.mark.parametrize("place", ["", "   "])
def test_geocode_blank_name_raises_without_http_call(place):
    with pytest.raises(geo.PlaceNotFoundError):
        geo.geocode(place, _client(_never))


def test_geocode_without_client_uses_own_client(monkeypatch):
    transport = httpx.MockTransport(_route(_json(KRAKOW), _never))
    real_client = httpx.Client
    monkeypatch.setattr(geo.httpx, "Client", lambda: real_client(transport=transport))
    assert geo.geocode("Kraków").lat == 50.06143


def test_unavailable_and_not_found_share_base_class():
    assert issubclass(geo.PlaceNotFoundError, geo.GeocodingError)
    assert issubclass(geo.GeocodingUnavailableError, geo.GeocodingError)


# =========================== models ==========================================

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


def test_nominatim_result_parses_strings():
    assert geo._NominatimResult.model_validate(POLITECHNIKA[0]).lat == 54.3718684
