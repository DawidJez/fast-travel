"""Deterministic time / cost / CO2 per transport mode from a distance.

Pure functions: no I/O, all numbers come from app.config. Public transport is an
estimate (average speed + flat ticket), not real timetables.
"""

from enum import Enum

from app import config


class Mode(str, Enum):
    WALK = "walk"
    BIKE = "bike"
    CAR = "car"
    PUBLIC_TRANSPORT = "public_transport"


def _speed_kmh(mode: Mode) -> float:
    return {
        Mode.WALK: config.WALK_SPEED_KMH,
        Mode.BIKE: config.BIKE_SPEED_KMH,
        Mode.CAR: config.CAR_SPEED_KMH,
        Mode.PUBLIC_TRANSPORT: config.PUBLIC_TRANSPORT_SPEED_KMH,
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


def travel_time_minutes(mode: Mode, distance_km: float) -> float:
    """Travel time in minutes at the mode's average door-to-door speed."""
    _check_distance(distance_km)
    return distance_km / _speed_kmh(mode) * 60


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


def co2_grams(mode: Mode, distance_km: float) -> float:
    """CO2e in grams per traveller (direct emissions)."""
    _check_distance(distance_km)
    return distance_km * _co2_g_per_km(mode)
