import pytest

from app import config
from app.services.calculators import Mode, ModeResult
from app.services.recommendation import (
    MODE_LABELS_PL,
    Recommendation,
    recommend,
    too_long,
    weather_exclusions,
)
from app.services.weather import Weather

GOOD = Weather(temperature_c=15, precipitation_mm=0, wind_speed_kmh=10)
RAIN = Weather(temperature_c=15, precipitation_mm=0.5, wind_speed_kmh=10)
WIND = Weather(temperature_c=15, precipitation_mm=0, wind_speed_kmh=45)
COLD = Weather(temperature_c=-3, precipitation_mm=0, wind_speed_kmh=10)


def R(mode, minutes, co2=0.0, cost=0.0):
    return ModeResult(mode=mode, time_minutes=minutes, cost_pln=cost, co2_grams=co2)


# Short trip: everything within the walk/bike time limits.
SHORT_TRIP = [
    R(Mode.WALK, 25),
    R(Mode.BIKE, 9),
    R(Mode.CAR, 10, co2=500, cost=3.5),
    R(Mode.PUBLIC_TRANSPORT, 22, co2=310, cost=6.0),
]

# Long trip: walking and cycling exceed the limits.
LONG_TRIP = [
    R(Mode.WALK, 120),
    R(Mode.BIKE, 48),
    R(Mode.CAR, 27, co2=2170, cost=15),
    R(Mode.PUBLIC_TRANSPORT, 48, co2=1350, cost=6),
]


# --- weather_exclusions ---

def test_good_weather_excludes_nothing():
    assert weather_exclusions(GOOD) == {}


def test_rain_excludes_walk_and_bike():
    assert weather_exclusions(RAIN) == {Mode.WALK: ["opady 0.5 mm"], Mode.BIKE: ["opady 0.5 mm"]}


def test_wind_excludes_walk_and_bike():
    assert weather_exclusions(WIND) == {Mode.WALK: ["silny wiatr 45 km/h"], Mode.BIKE: ["silny wiatr 45 km/h"]}


def test_frost_excludes_only_bike():
    assert weather_exclusions(COLD) == {Mode.BIKE: ["mróz -3 °C"]}


def test_storm_collects_all_reasons():
    storm = Weather(temperature_c=-1, precipitation_mm=2, wind_speed_kmh=60)
    assert weather_exclusions(storm) == {
        Mode.WALK: ["opady 2 mm", "silny wiatr 60 km/h"],
        Mode.BIKE: ["opady 2 mm", "silny wiatr 60 km/h", "mróz -1 °C"],
    }


def test_thresholds_inclusive_for_rain_and_wind_exclusive_for_frost():
    at_limits = Weather(
        temperature_c=config.FROST_THRESHOLD_C,
        precipitation_mm=config.RAIN_THRESHOLD_MM,
        wind_speed_kmh=config.STRONG_WIND_THRESHOLD_KMH,
    )
    assert weather_exclusions(at_limits) == {
        Mode.WALK: ["opady 0.1 mm", "silny wiatr 39 km/h"],
        Mode.BIKE: ["opady 0.1 mm", "silny wiatr 39 km/h"],
    }


def test_just_below_thresholds_is_fine():
    assert weather_exclusions(Weather(temperature_c=0.1, precipitation_mm=0.09, wind_speed_kmh=38.9)) == {}


# --- too_long ---

@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (R(Mode.WALK, 30), False),     # limit itself is fine
        (R(Mode.WALK, 30.1), True),
        (R(Mode.BIKE, 40), False),
        (R(Mode.BIKE, 40.1), True),
        (R(Mode.CAR, 500), False),     # no limit for motorised modes
        (R(Mode.PUBLIC_TRANSPORT, 500), False),
    ],
)
def test_too_long(result, expected):
    assert too_long(result) is expected


# --- recommend: weather cases ---

def test_good_weather_short_trip_bike_is_fastest():
    rec = recommend(GOOD, SHORT_TRIP)
    assert rec == Recommendation(mode=Mode.BIKE, reason="Najszybciej: rower (ok. 9 min, 0 g CO₂).")


def test_rain_drops_walk_and_bike_car_is_fastest():
    rec = recommend(RAIN, SHORT_TRIP)
    assert rec.mode is Mode.CAR
    assert rec.reason == (
        "Pieszo odpada (opady 0.5 mm); rower odpada (opady 0.5 mm). "
        "Najszybciej: samochód (ok. 10 min, 500 g CO₂)."
    )


def test_strong_wind_drops_walk_and_bike():
    rec = recommend(WIND, SHORT_TRIP)
    assert rec.mode is Mode.CAR
    assert rec.reason.startswith("Pieszo odpada (silny wiatr 45 km/h); rower odpada (silny wiatr 45 km/h).")


def test_frost_drops_only_bike():
    rec = recommend(COLD, SHORT_TRIP)
    assert rec.mode is Mode.CAR  # walk (25 min) is allowed but slower than the car (10 min)
    assert rec.reason == "Rower odpada (mróz -3 °C). Najszybciej: samochód (ok. 10 min, 500 g CO₂)."


def test_frost_walking_wins_when_fastest_remaining():
    trip = [R(Mode.WALK, 6), R(Mode.BIKE, 3), R(Mode.CAR, 8, co2=300), R(Mode.PUBLIC_TRANSPORT, 17, co2=150)]
    assert recommend(COLD, trip).mode is Mode.WALK


def test_frost_too_long_walk_is_dropped_as_well():
    trip = [R(Mode.WALK, 45), R(Mode.BIKE, 15), R(Mode.CAR, 12, co2=600), R(Mode.PUBLIC_TRANSPORT, 25, co2=380)]
    rec = recommend(COLD, trip)
    assert rec.mode is Mode.CAR
    assert rec.reason.startswith("Pieszo odpada (ok. 45 min, za długo); rower odpada (mróz -3 °C).")


# --- recommend: time limits and speed priority ---

def test_long_trip_good_weather_drops_walk_and_bike_by_time():
    rec = recommend(GOOD, LONG_TRIP)
    assert rec.mode is Mode.CAR
    assert rec.reason == (
        "Pieszo odpada (ok. 120 min, za długo); rower odpada (ok. 48 min, za długo). "
        "Najszybciej: samochód (ok. 27 min, 2170 g CO₂)."
    )


def test_time_beats_co2():
    results = [R(Mode.CAR, 10, co2=500), R(Mode.PUBLIC_TRANSPORT, 40, co2=300)]
    assert recommend(GOOD, results).mode is Mode.CAR


def test_public_transport_wins_when_faster():
    results = [R(Mode.CAR, 40, co2=900), R(Mode.PUBLIC_TRANSPORT, 35, co2=500)]
    assert recommend(RAIN, results).mode is Mode.PUBLIC_TRANSPORT


# --- ties ---

def test_equal_time_goes_to_lower_co2():
    results = [R(Mode.CAR, 20, co2=1670, cost=11.5), R(Mode.PUBLIC_TRANSPORT, 20, co2=1040, cost=6.0)]
    rec = recommend(GOOD, results)
    assert rec.mode is Mode.PUBLIC_TRANSPORT
    assert rec.reason == (
        "Najszybciej: komunikacja miejska (ok. 20 min, 1040 g CO₂), "
        "przy równym czasie wybrano niższą emisję CO₂."
    )


def test_bike_beats_car_on_equal_minutes_thanks_to_co2():
    results = [R(Mode.BIKE, 9.6), R(Mode.CAR, 9.6, co2=600)]
    assert recommend(GOOD, results).mode is Mode.BIKE


def test_time_compared_in_whole_minutes():
    results = [R(Mode.CAR, 19.6, co2=900), R(Mode.PUBLIC_TRANSPORT, 20.4, co2=500)]
    assert recommend(GOOD, results).mode is Mode.PUBLIC_TRANSPORT


def test_equal_time_and_co2_goes_to_lower_cost():
    results = [R(Mode.CAR, 10, co2=100, cost=5), R(Mode.PUBLIC_TRANSPORT, 10, co2=100, cost=3)]
    assert recommend(GOOD, results).mode is Mode.PUBLIC_TRANSPORT


def test_no_tie_note_with_clear_winner():
    assert "równym czasie" not in recommend(GOOD, SHORT_TRIP).reason


# --- errors ---

def test_empty_results_raises():
    with pytest.raises(ValueError, match="must not be empty"):
        recommend(GOOD, [])


def test_nothing_left_raises():
    with pytest.raises(ValueError, match="no mode left"):
        recommend(RAIN, [R(Mode.WALK, 10), R(Mode.BIKE, 5)])


def test_nothing_left_because_of_time_raises():
    with pytest.raises(ValueError, match="no mode left"):
        recommend(GOOD, [R(Mode.WALK, 100), R(Mode.BIKE, 100)])


# --- misc ---

def test_reason_keeps_unit_capitalisation():
    rec = recommend(COLD, [R(Mode.BIKE, 10), R(Mode.PUBLIC_TRANSPORT, 20, co2=100)])
    assert rec.reason.startswith("Rower odpada (mróz -3 °C).")


def test_every_mode_has_polish_label():
    assert set(MODE_LABELS_PL) == set(Mode)


def test_mode_result_is_frozen():
    result = R(Mode.CAR, 10)
    with pytest.raises(AttributeError):
        result.time_minutes = 5
