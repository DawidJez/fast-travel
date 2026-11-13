import math

import pytest

from app import config
from app.services.calculators import Mode
from app.services.distance import haversine_km, route_distance_km
from app.services.geo import Coordinates

R = config.EARTH_RADIUS_KM


def P(lat, lon):
    return Coordinates(lat=lat, lon=lon)


# Exact geometric cases: on a sphere these distances follow from the radius alone.

def test_one_degree_along_equator():
    assert haversine_km(P(0, 0), P(0, 1)) == pytest.approx(2 * math.pi * R / 360, rel=1e-12)  # 111.195 km


def test_one_degree_along_meridian():
    assert haversine_km(P(10, 20), P(11, 20)) == pytest.approx(2 * math.pi * R / 360, rel=1e-12)


def test_equator_to_pole_is_quarter_circumference():
    assert haversine_km(P(0, 0), P(90, 0)) == pytest.approx(math.pi * R / 2, rel=1e-12)  # 10 007.6 km


def test_antipodal_points_are_half_circumference():
    assert haversine_km(P(0, 0), P(0, 180)) == pytest.approx(math.pi * R, rel=1e-12)
    assert haversine_km(P(50, 20), P(-50, -160)) == pytest.approx(math.pi * R, rel=1e-9)


def test_crossing_antimeridian_takes_short_way():
    assert haversine_km(P(0, 179.5), P(0, -179.5)) == pytest.approx(2 * math.pi * R / 360, rel=1e-9)


# Real city pair with a published great-circle distance.

def test_gdansk_to_warsaw_known_distance():
    # City centres Gdańsk (54.35205, 18.64637) - Warszawa (52.22977, 21.01178):
    # 283 km in a straight line (https://travelandtime.com/flight-time-from-gdansk-to-warsaw).
    # Airport-to-airport figures (~296 km) differ because the points differ.
    gdansk, warsaw = P(54.35205, 18.64637), P(52.22977, 21.01178)
    assert haversine_km(gdansk, warsaw) == pytest.approx(283, abs=1)


def test_same_point_is_zero():
    assert haversine_km(P(54.35, 18.65), P(54.35, 18.65)) == 0.0


def test_distance_is_symmetric():
    a, b = P(54.35, 18.65), P(54.52, 18.53)
    assert haversine_km(a, b) == haversine_km(b, a)


# --- route distance per mode ---

@pytest.mark.parametrize(
    ("mode", "factor_name"),
    [
        (Mode.WALK, "WALK_DETOUR_FACTOR"),
        (Mode.BIKE, "BIKE_DETOUR_FACTOR"),
        (Mode.CAR, "DETOUR_FACTOR"),
        (Mode.PUBLIC_TRANSPORT, "DETOUR_FACTOR"),
    ],
)
def test_route_distance_uses_mode_detour_factor(monkeypatch, mode, factor_name):
    monkeypatch.setattr(config, factor_name, 2.0)
    assert route_distance_km(mode, 10) == pytest.approx(20)


def test_route_distance_real_factors():
    assert route_distance_km(Mode.WALK, 10) == pytest.approx(12)
    assert route_distance_km(Mode.BIKE, 10) == pytest.approx(12)
    assert route_distance_km(Mode.CAR, 10) == pytest.approx(13)
    assert route_distance_km(Mode.PUBLIC_TRANSPORT, 10) == pytest.approx(13)


def test_route_distance_negative_raises():
    with pytest.raises(ValueError):
        route_distance_km(Mode.CAR, -1)


