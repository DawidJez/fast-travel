"""Current weather at a point, via the Open-Meteo Forecast API ("now", no departure time)."""

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app import config
from app.services.geo import Coordinates


class WeatherUnavailableError(Exception):
    """The weather service timed out, could not be reached or answered with garbage."""


class Weather(BaseModel):
    """Conditions now. precipitation_mm = sum over the last 15 minutes."""

    model_config = ConfigDict(frozen=True)

    temperature_c: float
    precipitation_mm: float = Field(ge=0)
    wind_speed_kmh: float = Field(ge=0)


class _Current(BaseModel):
    """The API's "current" object (only the fields we use)."""

    temperature_2m: float
    precipitation: float = Field(ge=0)
    wind_speed_10m: float = Field(ge=0)


class _ForecastResponse(BaseModel):
    current: _Current


def current_weather(point: Coordinates, client: httpx.Client | None = None) -> Weather:
    """Return the weather now at `point`.

    Raises WeatherUnavailableError on timeout, network error, non-2xx status or an
    unexpected response body. Pass `client` to reuse a connection or inject a mock.
    """
    if client is None:
        with httpx.Client() as own_client:
            return current_weather(point, own_client)

    params = {
        "latitude": point.lat,
        "longitude": point.lon,
        "current": config.WEATHER_CURRENT_VARIABLES,
        "timezone": "auto",
    }
    try:
        response = client.get(config.WEATHER_URL, params=params, timeout=config.WEATHER_TIMEOUT_SECONDS)
        response.raise_for_status()
        body = _ForecastResponse.model_validate(response.json())
    except httpx.TimeoutException as exc:
        raise WeatherUnavailableError(
            f"Weather service did not answer within {config.WEATHER_TIMEOUT_SECONDS:g} s"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise WeatherUnavailableError(f"Weather service returned HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise WeatherUnavailableError(f"Weather service is unreachable: {exc}") from exc
    except ValueError as exc:  # invalid JSON or unexpected shape (pydantic ValidationError is a ValueError)
        raise WeatherUnavailableError("Weather service returned an unexpected response") from exc

    now = body.current
    return Weather(
        temperature_c=now.temperature_2m,
        precipitation_mm=now.precipitation,
        wind_speed_kmh=now.wind_speed_10m,
    )
