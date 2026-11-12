"""API schemas (request/response bodies) for trips."""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app import config
from app.services.calculators import Mode  # pure module (imports only config): no import cycle

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=config.TRIP_NAME_MAX_LENGTH)
]
Place = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=config.TRIP_PLACE_MAX_LENGTH)
]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=config.TRIP_NOTES_MAX_LENGTH)]
Latitude = Annotated[float, Field(ge=config.LATITUDE_MIN, le=config.LATITUDE_MAX, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=config.LONGITUDE_MIN, le=config.LONGITUDE_MAX, allow_inf_nan=False)]

COORDINATE_PAIRS = (("origin_lat", "origin_lon"), ("destination_lat", "destination_lon"))


class _TripOptionalFields(BaseModel):
    """Fields that are optional both when creating and when editing a trip."""

    notes: Notes | None = None
    origin_lat: Latitude | None = None
    origin_lon: Longitude | None = None
    destination_lat: Latitude | None = None
    destination_lon: Longitude | None = None

    @field_validator("notes")
    @classmethod
    def blank_notes_to_none(cls, value: str | None) -> str | None:
        """Store whitespace-only notes as no notes."""
        return value or None

    @model_validator(mode="after")
    def coordinates_come_in_pairs(self):
        """lat and lon of one place are either both set or both empty."""
        for lat, lon in COORDINATE_PAIRS:
            if (getattr(self, lat) is None) != (getattr(self, lon) is None):
                raise ValueError(f"{lat} and {lon} must be given together")
        return self


class TripCreate(_TripOptionalFields):
    """Body of POST /api/trips."""

    name: Name
    origin: Place
    destination: Place


class TripUpdate(_TripOptionalFields):
    """Body of PUT /api/trips/{id}: partial — only fields that are sent are changed."""

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

    @model_validator(mode="after")
    def coordinate_pairs_sent_together(self):
        """A partial update must not change only one half of a lat/lon pair."""
        for lat, lon in COORDINATE_PAIRS:
            if (lat in self.model_fields_set) != (lon in self.model_fields_set):
                raise ValueError(f"{lat} and {lon} must be sent together")
        return self


class TripRead(BaseModel):
    """Trip as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    origin: str
    destination: str
    notes: str | None
    origin_lat: float | None
    origin_lon: float | None
    destination_lat: float | None
    destination_lon: float | None
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
