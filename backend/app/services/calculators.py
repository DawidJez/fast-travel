"""Deterministic time / cost / CO2 per transport mode from a distance.

Pure functions: no I/O, all numbers come from app.config. Public transport is an
estimate (average speed + flat ticket), not real timetables.
"""

from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum
from zoneinfo import ZoneInfo

from app import config


class Mode(str, Enum):
    WALK = "walk"
    BIKE = "bike"
    CAR = "car"
    PUBLIC_TRANSPORT = "public_transport"


@dataclass(frozen=True)
class ModeResult:
    """Computed figures for one mode on one trip."""

    mode: Mode
    time_minutes: float
    cost_pln: float
    co2_grams: float


def _speed_kmh(mode: Mode) -> float:
    return {
        Mode.WALK: config.WALK_SPEED_KMH,
        Mode.BIKE: config.BIKE_SPEED_KMH,
        Mode.CAR: config.CAR_SPEED_KMH,
        Mode.PUBLIC_TRANSPORT: config.PUBLIC_TRANSPORT_SPEED_KMH,
    }[mode]


def _overhead_minutes(mode: Mode) -> float:
    return {
        Mode.WALK: config.WALK_OVERHEAD_MINUTES,
        Mode.BIKE: config.BIKE_OVERHEAD_MINUTES,
        Mode.CAR: config.CAR_OVERHEAD_MINUTES,
        Mode.PUBLIC_TRANSPORT: config.PUBLIC_TRANSPORT_OVERHEAD_MINUTES,
    }[mode]


def _co2_g_per_km(mode: Mode) -> float:
    return {
        Mode.WALK: config.WALK_CO2_G_PER_KM,
        Mode.BIKE: config.BIKE_CO2_G_PER_KM,
        Mode.CAR: config.CAR_CO2_G_PER_KM,
        Mode.PUBLIC_TRANSPORT: config.PUBLIC_TRANSPORT_CO2_G_PER_KM,
    }[mode]


def _check_distance(distance_km: float) -> None:
    if distance_km < 0:
        raise ValueError(f"distance_km must be >= 0, got {distance_km}")


def is_car_peak(now: datetime) -> bool:
    """True if `now` (local time, LOCAL_TIMEZONE) falls in a car rush-hour window [start, end).

    Aware datetimes are converted to local time; naive ones are taken as local time already.
    """
    if now.tzinfo is not None:
        now = now.astimezone(ZoneInfo(config.LOCAL_TIMEZONE))
    clock = now.time().replace(tzinfo=None)
    return any(time.fromisoformat(start) <= clock < time.fromisoformat(end) for start, end in config.CAR_PEAK_WINDOWS)


def travel_time_minutes(mode: Mode, distance_km: float, peak: bool = False) -> float:
    """Door-to-door minutes: distance at the mode's average speed + its fixed per-trip
    overhead (parking search for car, walk + wait for public transport), plus the car
    rush-hour penalty when `peak` is True. 0 km -> 0 min."""
    _check_distance(distance_km)
    if distance_km == 0:
        return 0.0
    minutes = distance_km / _speed_kmh(mode) * 60 + _overhead_minutes(mode)
    if peak and mode is Mode.CAR:
        minutes += config.CAR_PEAK_PENALTY_MINUTES
    return minutes


def cost_pln(mode: Mode, distance_km: float) -> float:
    """Cost in PLN: per km for car/bike/walk, one flat ticket for public transport (0 for 0 km)."""
    _check_distance(distance_km)
    if mode is Mode.PUBLIC_TRANSPORT:
        return config.PUBLIC_TRANSPORT_TICKET_PLN if distance_km > 0 else 0.0
    per_km = {
        Mode.WALK: config.WALK_COST_PLN_PER_KM,
        Mode.BIKE: config.BIKE_COST_PLN_PER_KM,
        Mode.CAR: config.CAR_COST_PLN_PER_KM,
    }[mode]
    return distance_km * per_km


def co2_grams(mode: Mode, distance_km: float, peak: bool = False) -> float:
    """CO2e in grams per traveller (direct emissions), plus the extra idling emissions of a
    car stuck in rush hour when `peak` is True. 0 km -> 0 g."""
    _check_distance(distance_km)
    grams = distance_km * _co2_g_per_km(mode)
    if peak and mode is Mode.CAR and distance_km > 0:
        grams += config.CAR_PEAK_EXTRA_CO2_G
    return grams
