"""Geocoding: place name -> coordinates.

Primary: Open-Meteo Geocoding (towns, districts). Fallback: Nominatim / OpenStreetMap
(addresses, POIs like "Politechnika Gdańska", "City District"), used only when Open-Meteo
finds nothing or is unavailable. Nominatim usage policy is enforced here: own User-Agent,
max 1 request/s for the whole app, in-memory cache, can be switched off via env var.
"""

import threading
import time
from collections import OrderedDict

import httpx
from pydantic import BaseModel, ConfigDict

from app import config
from app.schemas import Latitude, Longitude


class GeocodingError(Exception):
    """Base class for geocoding failures."""


class PlaceNotFoundError(GeocodingError):
    """No geocoding service has a match for the given place name."""

    def __init__(self, place: str):
        self.place = place
        super().__init__(f"Place not found: {place!r}")


class GeocodingUnavailableError(GeocodingError):
    """The geocoding service timed out, could not be reached or answered with garbage."""


class Coordinates(BaseModel):
    """A point in WGS 84 degrees."""

    model_config = ConfigDict(frozen=True)

    lat: Latitude
    lon: Longitude


# --- shared HTTP handling -----------------------------------------------------

def _get_json(client: httpx.Client, service: str, url: str, params: dict, headers: dict | None = None):
    """GET and decode JSON; map every transport/HTTP/JSON failure to GeocodingUnavailableError."""
    try:
        response = client.get(url, params=params, headers=headers, timeout=config.GEOCODING_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException as exc:
        raise GeocodingUnavailableError(
            f"{service} did not answer within {config.GEOCODING_TIMEOUT_SECONDS:g} s"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise GeocodingUnavailableError(f"{service} returned HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise GeocodingUnavailableError(f"{service} is unreachable: {exc}") from exc
    except ValueError as exc:  # invalid JSON
        raise GeocodingUnavailableError(f"{service} returned an unexpected response") from exc


# --- Open-Meteo ---------------------------------------------------------------

class _GeoResult(BaseModel):
    """One entry of Open-Meteo's "results" list (only the fields we use)."""

    latitude: Latitude
    longitude: Longitude


class _GeoResponse(BaseModel):
    """Open-Meteo response body; "results" is missing entirely when nothing matches."""

    results: list[_GeoResult] = []


def geocode_open_meteo(name: str, client: httpx.Client) -> Coordinates:
    """First Open-Meteo match for `name` (filtered to GEOCODING_COUNTRY_CODE)."""
    params = {
        "name": name,
        "count": 1,
        "language": config.GEOCODING_LANGUAGE,
        "countryCode": config.GEOCODING_COUNTRY_CODE,
        "format": "json",
    }
    payload = _get_json(client, "Geocoding service", config.GEOCODING_URL, params)
    try:
        body = _GeoResponse.model_validate(payload)
    except ValueError as exc:  # pydantic ValidationError is a ValueError
        raise GeocodingUnavailableError("Geocoding service returned an unexpected response") from exc
    if not body.results:
        raise PlaceNotFoundError(name)
    best = body.results[0]
    return Coordinates(lat=best.latitude, lon=best.longitude)


# --- Nominatim ----------------------------------------------------------------

class _NominatimResult(BaseModel):
    """One Nominatim result; lat/lon come as strings and are parsed to floats."""

    lat: Latitude
    lon: Longitude


_nominatim_lock = threading.Lock()
_nominatim_last_request = float("-inf")
_nominatim_cache: "OrderedDict[str, Coordinates | None]" = OrderedDict()


def _nominatim_throttle() -> None:
    """Block so that requests are at least NOMINATIM_MIN_INTERVAL_SECONDS apart (caller holds the lock)."""
    global _nominatim_last_request
    wait = _nominatim_last_request + config.NOMINATIM_MIN_INTERVAL_SECONDS - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _nominatim_last_request = time.monotonic()


def _cache_put(key: str, value: Coordinates | None) -> None:
    _nominatim_cache[key] = value
    _nominatim_cache.move_to_end(key)
    while len(_nominatim_cache) > config.NOMINATIM_CACHE_SIZE:
        _nominatim_cache.popitem(last=False)


def clear_nominatim_cache() -> None:
    """Forget cached Nominatim answers (used by tests)."""
    _nominatim_cache.clear()


def geocode_nominatim(name: str, client: httpx.Client) -> Coordinates:
    """First Nominatim match for `name` in Poland, throttled and cached per the usage policy.

    Both hits and "not found" answers are cached; errors are not.
    """
    key = name.casefold()
    with _nominatim_lock:
        if key in _nominatim_cache:
            _nominatim_cache.move_to_end(key)
            cached = _nominatim_cache[key]
        else:
            _nominatim_throttle()
            params = {
                "q": name,
                "format": "jsonv2",
                "limit": 1,
                "countrycodes": config.GEOCODING_COUNTRY_CODE.lower(),
                "accept-language": config.GEOCODING_LANGUAGE,
            }
            payload = _get_json(
                client, "Nominatim", config.NOMINATIM_URL, params, headers={"User-Agent": config.NOMINATIM_USER_AGENT}
            )
            try:
                results = [_NominatimResult.model_validate(item) for item in payload]
            except (TypeError, ValueError) as exc:  # not a list / bad items
                raise GeocodingUnavailableError("Nominatim returned an unexpected response") from exc
            cached = Coordinates(lat=results[0].lat, lon=results[0].lon) if results else None
            _cache_put(key, cached)
    if cached is None:
        raise PlaceNotFoundError(name)
    return cached


# --- combined -----------------------------------------------------------------

def geocode(place: str, client: httpx.Client | None = None) -> Coordinates:
    """Coordinates of `place`: Open-Meteo first, Nominatim if Open-Meteo finds nothing or fails.

    Raises PlaceNotFoundError only when every service answered "no match", and
    GeocodingUnavailableError when no service found it and at least one failed.
    Pass `client` to reuse a connection (or to inject a mock transport in tests).
    """
    name = place.strip()
    if not name:
        raise PlaceNotFoundError(place)

    if client is None:
        with httpx.Client() as own_client:
            return geocode(name, own_client)

    providers = [geocode_open_meteo]
    if config.NOMINATIM_ENABLED:
        providers.append(geocode_nominatim)

    unavailable: GeocodingUnavailableError | None = None
    for provider in providers:
        try:
            return provider(name, client)
        except PlaceNotFoundError:
            continue
        except GeocodingUnavailableError as exc:
            unavailable = unavailable or exc
    if unavailable is not None:
        raise unavailable
    raise PlaceNotFoundError(name)
