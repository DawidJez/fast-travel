"""API schemas (request/response bodies) for trips."""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app import config
from app.services.calculators import Mode  # pure module (imports only config): no import cycle
from app.services.parsing import Source

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=config.TRIP_NAME_MAX_LENGTH)
]
Place = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=config.TRIP_PLACE_MAX_LENGTH)
]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=config.TRIP_NOTES_MAX_LENGTH)]
Latitude = Annotated[float, Field(ge=config.LATITUDE_MIN, le=config.LATITUDE_MAX, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=config.LONGITUDE_MIN, le=config.LONGITUDE_MAX, allow_inf_nan=False)]

class _TripOptionalFields(BaseModel):
    """Fields that are optional both when creating and when editing a trip.

    Coordinates are not accepted from the client: the server sets them by geocoding.
    Unknown fields (including any *_lat / *_lon sent by a client) are ignored.
    """

    notes: Notes | None = None

    @field_validator("notes")
    @classmethod
    def blank_notes_to_none(cls, value: str | None) -> str | None:
        """Store whitespace-only notes as no notes."""
        return value or None


class TripCreate(_TripOptionalFields):
    """Body of POST /api/trips. Origin and destination are geocoded by the server."""

    name: Name
    origin: Place
    destination: Place


class TripUpdate(_TripOptionalFields):
    """Body of PUT /api/trips/{id}: partial — only fields that are sent are changed.
    A changed origin / destination is geocoded again by the server."""

    name: Name | None = None
    origin: Place | None = None
    destination: Place | None = None

    @field_validator("name", "origin", "destination")
    @classmethod
    def reject_explicit_null(cls, value: str | None) -> str:
        """Required trip fields may be omitted, but not cleared with null."""
        if value is None:
            raise ValueError("field cannot be null; omit it to keep the current value")
        return value


class TripRead(BaseModel):
    """Trip as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    origin: str
    destination: str
    notes: str | None
    origin_lat: float
    origin_lon: float
    destination_lat: float
    destination_lon: float
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def assume_utc(cls, value: datetime) -> datetime:
        """SQLite drops timezone info; stored timestamps are UTC, so re-attach it."""
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# --- Comparison (GET /api/trips/{id}/comparison) ---


class ModeComparisonRead(BaseModel):
    """Figures for one transport mode. Rounded for display; computed unrounded."""

    mode: Mode
    distance_km: float = Field(description="Estimated route length, 1 decimal")
    time_minutes: float = Field(description="Door-to-door estimate, 1 decimal")
    cost_pln: float = Field(description="2 decimals")
    co2_grams: int = Field(description="Direct CO2e per traveller, whole grams")
    estimate: bool = Field(description="True when the figures are a rough estimate (public transport)")
    note: str | None = Field(description="Explanation of the estimate; null for other modes")


class WeatherRead(BaseModel):
    """Weather now at the trip origin."""

    temperature_c: float
    precipitation_mm: float
    wind_speed_kmh: float


class RecommendationRead(BaseModel):
    mode: Mode
    reason: str


class TripComparisonRead(BaseModel):
    """Body of GET /api/trips/{id}/comparison."""

    trip_id: int
    origin: str
    destination: str
    straight_line_km: float = Field(description="Great-circle distance, 1 decimal")
    car_peak: bool = Field(description="True if the car rush-hour penalty was applied (local time now)")
    weather: WeatherRead | None = Field(description="null when the weather service is unavailable")
    modes: list[ModeComparisonRead]
    recommendation: RecommendationRead


# --- AI parsing (POST /api/parse) ---


class ParseRequest(BaseModel):
    """Body of POST /api/parse: a free-text trip description."""

    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=config.PARSE_TEXT_MAX_LENGTH)
    ]


class ParseResponse(BaseModel):
    """Fields to prefill the trip form; null when the text does not say. Only text, never numbers."""

    name: str | None
    origin: str | None
    destination: str | None
    source: Source = Field(description='"llm" = Gemini, "demo" = rule-based parser (no API key or LLM failure)')
