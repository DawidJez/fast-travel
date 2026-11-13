"""Calculator tests on simple numbers. Constants are patched to round values so the
expected results are obvious, plus one check against the real config values."""

from datetime import datetime, timezone

import pytest

from app import config
from app.services import calculators as calc
from app.services.calculators import Mode

ROUND_CONSTANTS = {
    "WALK_SPEED_KMH": 5.0,
    "BIKE_SPEED_KMH": 15.0,
    "CAR_SPEED_KMH": 30.0,
    "PUBLIC_TRANSPORT_SPEED_KMH": 20.0,
    "WALK_OVERHEAD_MINUTES": 0.0,
    "BIKE_OVERHEAD_MINUTES": 0.0,
    "CAR_OVERHEAD_MINUTES": 0.0,
    "PUBLIC_TRANSPORT_OVERHEAD_MINUTES": 0.0,
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


@pytest.mark.parametrize(
    ("mode", "overhead", "distance", "minutes"),
    [
        (Mode.CAR, 5, 30, 65),                # 60 min driving + 5 min parking
        (Mode.CAR, 5, 10, 25),
        (Mode.PUBLIC_TRANSPORT, 10, 20, 70),  # 60 min riding + 10 min walk/wait
        (Mode.BIKE, 0, 15, 60),
    ],
)
def test_travel_time_adds_overhead(round_config, monkeypatch, mode, overhead, distance, minutes):
    name = {Mode.CAR: "CAR", Mode.PUBLIC_TRANSPORT: "PUBLIC_TRANSPORT", Mode.BIKE: "BIKE"}[mode]
    monkeypatch.setattr(config, f"{name}_OVERHEAD_MINUTES", overhead)
    assert calc.travel_time_minutes(mode, distance) == pytest.approx(minutes)


@pytest.mark.parametrize("mode", list(Mode))
def test_travel_time_zero_distance_is_zero_even_with_overhead(round_config, monkeypatch, mode):
    monkeypatch.setattr(config, "CAR_OVERHEAD_MINUTES", 5)
    monkeypatch.setattr(config, "PUBLIC_TRANSPORT_OVERHEAD_MINUTES", 10)
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


# --- car rush hour ---

@pytest.mark.parametrize(
    ("hhmm", "expected"),
    [
        ("07:29", False),
        ("07:30", True),    # start inclusive
        ("08:00", True),
        ("08:29", True),
        ("08:30", False),   # end exclusive
        ("12:00", False),
        ("14:59", False),
        ("15:00", True),
        ("16:59", True),
        ("17:00", False),
        ("23:00", False),
    ],
)
def test_is_car_peak_naive_local_time(hhmm, expected):
    h, m = map(int, hhmm.split(":"))
    assert calc.is_car_peak(datetime(2026, 11, 12, h, m)) is expected


def test_is_car_peak_converts_aware_utc_to_warsaw():
    # 06:45 UTC in November (CET, UTC+1) = 07:45 in Warsaw -> peak
    assert calc.is_car_peak(datetime(2026, 11, 12, 6, 45, tzinfo=timezone.utc)) is True
    # 07:45 UTC = 08:45 in Warsaw -> no longer peak
    assert calc.is_car_peak(datetime(2026, 11, 12, 7, 45, tzinfo=timezone.utc)) is False


def test_is_car_peak_handles_summer_time():
    # 13:30 UTC in July (CEST, UTC+2) = 15:30 in Warsaw -> peak
    assert calc.is_car_peak(datetime(2026, 7, 1, 13, 30, tzinfo=timezone.utc)) is True


def test_peak_penalty_applies_to_car_only(round_config, monkeypatch):
    monkeypatch.setattr(config, "CAR_PEAK_PENALTY_MINUTES", 10)
    assert calc.travel_time_minutes(Mode.CAR, 30, peak=True) == pytest.approx(70)
    assert calc.travel_time_minutes(Mode.CAR, 30, peak=False) == pytest.approx(60)
    for mode in (Mode.WALK, Mode.BIKE, Mode.PUBLIC_TRANSPORT):
        assert calc.travel_time_minutes(mode, 10, peak=True) == calc.travel_time_minutes(mode, 10)


def test_peak_penalty_not_added_for_zero_distance(round_config):
    assert calc.travel_time_minutes(Mode.CAR, 0, peak=True) == 0


def test_real_peak_penalty_is_midpoint_of_8_to_15():
    assert config.CAR_PEAK_PENALTY_MINUTES == pytest.approx((8 + 15) / 2)


# --- real config values (catches a wrong constant wired to a mode) ---

def test_real_config_public_transport_overhead_is_derived():
    # 2 x 390 m at 5 km/h = 9.36 min walking + 5 min waiting
    assert config.PUBLIC_TRANSPORT_OVERHEAD_MINUTES == pytest.approx(14.36)


def test_real_config_10_km():
    assert calc.travel_time_minutes(Mode.CAR, 10) == pytest.approx(10 / 25.6 * 60 + 4)
    assert calc.travel_time_minutes(Mode.PUBLIC_TRANSPORT, 10) == pytest.approx(10 / 17.7 * 60 + 14.36)
    assert calc.travel_time_minutes(Mode.BIKE, 10) == pytest.approx(40)
    assert calc.travel_time_minutes(Mode.WALK, 10) == pytest.approx(120)
    assert calc.cost_pln(Mode.CAR, 10) == pytest.approx(11.5)
    assert calc.cost_pln(Mode.PUBLIC_TRANSPORT, 10) == pytest.approx(6.0)
    assert calc.co2_grams(Mode.CAR, 10) == pytest.approx(1670)
    assert calc.co2_grams(Mode.PUBLIC_TRANSPORT, 10) == pytest.approx(1040)


# --- car rush hour CO2 ---

def test_peak_extra_co2_applies_to_car_only(round_config, monkeypatch):
    monkeypatch.setattr(config, "CAR_PEAK_EXTRA_CO2_G", 300)
    assert calc.co2_grams(Mode.CAR, 10, peak=True) == pytest.approx(1300)
    assert calc.co2_grams(Mode.CAR, 10, peak=False) == pytest.approx(1000)
    assert calc.co2_grams(Mode.PUBLIC_TRANSPORT, 10, peak=True) == pytest.approx(500)
    assert calc.co2_grams(Mode.BIKE, 10, peak=True) == 0


def test_peak_extra_co2_not_added_for_zero_distance(round_config):
    assert calc.co2_grams(Mode.CAR, 0, peak=True) == 0


def test_real_peak_extra_co2_is_idling_for_penalty_minutes():
    # 11.5 min idling at 0.9 L/h of petrol at 2069.16 g CO2e/L
    assert config.CAR_IDLE_FUEL_L_PER_HOUR == pytest.approx(0.9)
    assert config.CAR_PEAK_EXTRA_CO2_G == pytest.approx(11.5 / 60 * 0.9 * 2069.16)
    assert config.CAR_PEAK_EXTRA_CO2_G == pytest.approx(356.9, abs=0.1)
