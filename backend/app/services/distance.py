"""Distance between two points: great-circle (haversine) and estimated road distance."""

import math

from app import config
from app.services.geo import Coordinates


def haversine_km(a: Coordinates, b: Coordinates) -> float:
    """Great-circle ("as the crow flies") distance in km on a spherical Earth."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    # min() guards against h drifting a hair above 1.0 from float rounding (antipodal points).
    return 2 * config.EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, h)))


def road_distance_km(a: Coordinates, b: Coordinates) -> float:
    """Estimated road distance: haversine x detour factor (roads are not straight lines)."""
    return haversine_km(a, b) * config.DETOUR_FACTOR
