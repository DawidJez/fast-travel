"""Database table models."""

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel

from app import config


def utc_now() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Trip(SQLModel, table=True):
    """A saved trip. Coordinates are optional until geocoding fills them."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=config.TRIP_NAME_MAX_LENGTH)
    origin: str = Field(max_length=config.TRIP_PLACE_MAX_LENGTH)
    destination: str = Field(max_length=config.TRIP_PLACE_MAX_LENGTH)
    notes: str | None = Field(default=None, max_length=config.TRIP_NOTES_MAX_LENGTH)
    origin_lat: float | None = None
    origin_lon: float | None = None
    destination_lat: float | None = None
    destination_lon: float | None = None
    created_at: datetime = Field(default_factory=utc_now)
