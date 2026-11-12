"""Geocoding: place name -> coordinates, via the Open-Meteo Geocoding API."""

import httpx
from pydantic import BaseModel, ConfigDict

from app import config
from app.schemas import Latitude, Longitude


class GeocodingError(Exception):
    """Base class for geocoding failures."""


class PlaceNotFoundError(GeocodingError):
    """The geocoding service has no match for the given place name."""

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


class _GeoResult(BaseModel):
    """One entry of the API's "results" list (only the fields we use)."""

    latitude: Latitude
    longitude: Longitude


class _GeoResponse(BaseModel):
    """API response body; "results" is missing entirely when nothing matches."""

    results: list[_GeoResult] = []


def geocode(place: str, client: httpx.Client | None = None) -> Coordinates:
    """Return the coordinates of the best match for `place`.

    Raises PlaceNotFoundError when there is no match and GeocodingUnavailableError
    on timeout, network error, non-2xx status or an unexpected response body.
    Pass `client` to reuse a connection (or to inject a mock transport in tests).
    """
    name = place.strip()
    if not name:
        raise PlaceNotFoundError(place)

    if client is None:
        with httpx.Client() as own_client:
            return geocode(name, own_client)

    params = {
        "name": name,
        "count": 1,
        "language": config.GEOCODING_LANGUAGE,
        "countryCode": config.GEOCODING_COUNTRY_CODE,
        "format": "json",
    }
    try:
        response = client.get(config.GEOCODING_URL, params=params, timeout=config.GEOCODING_TIMEOUT_SECONDS)
        response.raise_for_status()
        body = _GeoResponse.model_validate(response.json())
    except httpx.TimeoutException as exc:
        raise GeocodingUnavailableError(
            f"Geocoding service did not answer within {config.GEOCODING_TIMEOUT_SECONDS:g} s"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise GeocodingUnavailableError(
            f"Geocoding service returned HTTP {exc.response.status_code}"
        ) from exc
    except httpx.HTTPError as exc:
        raise GeocodingUnavailableError(f"Geocoding service is unreachable: {exc}") from exc
    except ValueError as exc:  # invalid JSON or unexpected shape (pydantic ValidationError is a ValueError)
        raise GeocodingUnavailableError("Geocoding service returned an unexpected response") from exc

    if not body.results:
        raise PlaceNotFoundError(name)
    best = body.results[0]
    return Coordinates(lat=best.latitude, lon=best.longitude)
