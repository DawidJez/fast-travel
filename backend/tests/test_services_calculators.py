"""Calculator tests on simple numbers. Constants are patched to round values so the
expected results are obvious, plus one check against the real config values."""

import pytest

from app import config
from app.services import calculators as calc
from app.services.calculators import Mode

ROUND_CONSTANTS = {
    "WALK_SPEED_KMH": 5.0,
    "BIKE_SPEED_KMH": 15.0,
    "CAR_SPEED_KMH": 30.0,
    "PUBLIC_TRANSPORT_SPEED_KMH": 20.0,
    "WALK_COST_PLN_PER_KM": 0.0,
    "BIKE_COST_PLN_PER_KM": 0.0,
    "CAR_COST_PLN_PER_KM": 1.0,
    "PUBLIC_TRANSPORT_TICKET_PLN": 5.0,
    "WALK_CO2_G_PER_KM": 0.0,
    "BIKE_CO2_G_PER_KM": 0.0,
    "CAR_CO2_G_PER_KM": 100.0,
    "PUBLIC_TRANSPORT_CO2_G_PER_KM": 50.0,
}


@pytest.fixture
def round_config(monkeypatch):
    for name, value in ROUND_CONSTANTS.items():
        monkeypatch.setattr(config, name, value)


def test_mode_values():
    assert [m.value for m in Mode] == ["walk", "bike", "car", "public_transport"]


# --- time ---

@pytest.mark.parametrize(
    ("mode", "distance", "minutes"),
    [
        (Mode.WALK, 5, 60),               # 5 km at 5 km/h
        (Mode.WALK, 1, 12),
        (Mode.BIKE, 15, 60),
        (Mode.BIKE, 5, 20),
        (Mode.CAR, 30, 60),
        (Mode.CAR, 10, 20),
        (Mode.PUBLIC_TRANSPORT, 20, 60),
        (Mode.PUBLIC_TRANSPORT, 10, 30),
    ],
)
def test_travel_time_minutes(round_config, mode, distance, minutes):
    assert calc.travel_time_minutes(mode, distance) == pytest.approx(minutes)


@pytest.mark.parametrize("mode", list(Mode))
def test_travel_time_zero_distance_is_zero(round_config, mode):
    assert calc.travel_time_minutes(mode, 0) == 0


# --- cost ---

@pytest.mark.parametrize(
    ("mode", "distance", "pln"),
    [
        (Mode.WALK, 10, 0),
        (Mode.BIKE, 10, 0),
        (Mode.CAR, 10, 10),
        (Mode.CAR, 2.5, 2.5),
        (Mode.PUBLIC_TRANSPORT, 1, 5),     # flat ticket
        (Mode.PUBLIC_TRANSPORT, 25, 5),    # same ticket for a longer trip
    ],
)
def test_cost_pln(round_config, mode, distance, pln):
    assert calc.cost_pln(mode, distance) == pytest.approx(pln)


@pytest.mark.parametrize("mode", list(Mode))
def test_cost_zero_distance_is_zero(round_config, mode):
    assert calc.cost_pln(mode, 0) == 0


# --- CO2 ---

@pytest.mark.parametrize(
    ("mode", "distance", "grams"),
    [
        (Mode.WALK, 10, 0),
        (Mode.BIKE, 10, 0),
        (Mode.CAR, 10, 1000),
        (Mode.PUBLIC_TRANSPORT, 10, 500),
        (Mode.CAR, 0.5, 50),
    ],
)
def test_co2_grams(round_config, mode, distance, grams):
    assert calc.co2_grams(mode, distance) == pytest.approx(grams)


# --- input checks ---

@pytest.mark.parametrize("func", [calc.travel_time_minutes, calc.cost_pln, calc.co2_grams])
@pytest.mark.parametrize("mode", list(Mode))
def test_negative_distance_raises(func, mode):
    with pytest.raises(ValueError, match="distance_km must be >= 0"):
        func(mode, -1)


# --- real config values (catches a wrong constant wired to a mode) ---

def test_real_config_10_km():
    assert calc.travel_time_minutes(Mode.CAR, 10) == pytest.approx(10 / config.CAR_SPEED_KMH * 60)
    assert calc.travel_time_minutes(Mode.PUBLIC_TRANSPORT, 10) == pytest.approx(10 / config.PUBLIC_TRANSPORT_SPEED_KMH * 60)
    assert calc.travel_time_minutes(Mode.BIKE, 10) == pytest.approx(40)
    assert calc.travel_time_minutes(Mode.WALK, 10) == pytest.approx(120)
    assert calc.cost_pln(Mode.CAR, 10) == pytest.approx(11.5)
    assert calc.cost_pln(Mode.PUBLIC_TRANSPORT, 10) == pytest.approx(6.0)
    assert calc.co2_grams(Mode.CAR, 10) == pytest.approx(1670)
    assert calc.co2_grams(Mode.PUBLIC_TRANSPORT, 10) == pytest.approx(1040)
