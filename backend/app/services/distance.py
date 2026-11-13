"""Distance: great-circle (haversine) between two points and estimated route length per mode."""

import math

from app import config
from app.services.calculators import Mode
from app.services.geo import Coordinates


def haversine_km(a: Coordinates, b: Coordinates) -> float:
    """Great-circle ("as the crow flies") distance in km on a spherical Earth."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    # min() guards against h drifting a hair above 1.0 from float rounding (antipodal points).
    return 2 * config.EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, h)))


def _detour_factor(mode: Mode) -> float:
    return {
        Mode.WALK: config.WALK_DETOUR_FACTOR,
        Mode.BIKE: config.BIKE_DETOUR_FACTOR,
        Mode.CAR: config.DETOUR_FACTOR,
        Mode.PUBLIC_TRANSPORT: config.DETOUR_FACTOR,
    }[mode]


def route_distance_km(mode: Mode, straight_line_km: float) -> float:
    """Estimated route length for `mode`: straight-line distance x the mode's detour factor
    (roads for car / public transport, more direct paths for walking and cycling)."""
    if straight_line_km < 0:
        raise ValueError(f"straight_line_km must be >= 0, got {straight_line_km}")
    return straight_line_km * _detour_factor(mode)
