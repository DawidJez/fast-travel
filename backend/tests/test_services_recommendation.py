import pytest

from app import config
from app.services.calculators import Mode, ModeResult
from app.services.recommendation import (
    MODE_LABELS_PL,
    MODE_LABELS_PL_GENITIVE,
    ZERO_EMISSION_MODES,
    Recommendation,
    format_pln,
    recommend,
    too_long,
    weather_exclusions,
    zero_emission_alternative,
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


def test_no_tie_note_when_tied_modes_have_equal_co2():
    zero = [R(m, 0) for m in Mode]  # zero-distance trip: everything 0 min, 0 g
    rec = recommend(GOOD, zero)
    assert rec.reason == "Najszybciej: pieszo (ok. 0 min, 0 g CO₂)."


def test_tie_note_only_when_a_tied_mode_emits_more():
    results = [R(Mode.WALK, 10), R(Mode.BIKE, 10), R(Mode.CAR, 10, co2=300)]
    assert "przy równym czasie wybrano niższą emisję CO₂" in recommend(GOOD, results).reason


def test_no_tie_note_with_clear_winner():
    assert "równym czasie" not in recommend(GOOD, SHORT_TRIP).reason


# --- zero-emission preference (+50% time rule) ---

# Car 20 min; bike 24 min (+20%) -> bike wins. Walk 29 min also within limits.
GREEN_TRIP = [
    R(Mode.WALK, 29),
    R(Mode.BIKE, 24.4),
    R(Mode.CAR, 19.5, co2=1104, cost=7.59),
    R(Mode.PUBLIC_TRANSPORT, 37, co2=690, cost=6.0),
]


def test_zero_emission_within_threshold_wins_with_cost_of_time_and_savings():
    rec = recommend(GOOD, GREEN_TRIP)
    assert rec == Recommendation(
        mode=Mode.BIKE,
        reason="Rower (ok. 24 min) zamiast samochodu (ok. 20 min): o 4 min dłużej, ale oszczędzasz 7,59 zł i 1104 g CO₂.",
    )


def test_zero_emission_just_below_threshold_wins():
    results = [R(Mode.BIKE, 14.4), R(Mode.CAR, 10, co2=500, cost=4)]  # shown 14 min < 15
    assert recommend(GOOD, results).mode is Mode.BIKE


def test_threshold_uses_whole_minutes_shown_in_text():
    # exact: 30.5 < 20.4 x 1.5 = 30.6, but the user sees 30 vs 20 = exactly +50% -> loses
    results = [R(Mode.BIKE, 30.5), R(Mode.CAR, 20.4, co2=900, cost=5)]
    rec = recommend(GOOD, results)
    assert rec.mode is Mode.CAR
    assert rec.reason == "Najszybciej: samochód (ok. 20 min, 900 g CO₂)."


def test_threshold_rounding_can_also_let_zero_emission_win():
    # exact: 29.6 >= 19.6 x 1.5 = 29.4, but shown 30 vs 20 -> still exactly +50% -> loses;
    # 29.4 vs 19.6 -> shown 29 vs 20 -> wins
    assert recommend(GOOD, [R(Mode.BIKE, 29.6), R(Mode.CAR, 19.6, co2=900)]).mode is Mode.CAR
    assert recommend(GOOD, [R(Mode.BIKE, 29.4), R(Mode.CAR, 19.6, co2=900)]).mode is Mode.BIKE


def test_zero_emission_exactly_at_threshold_loses():
    results = [R(Mode.BIKE, 15), R(Mode.CAR, 10, co2=500, cost=4)]  # 15 = 10 x 1.5, needs to be less
    rec = recommend(GOOD, results)
    assert rec.mode is Mode.CAR
    assert rec.reason == "Najszybciej: samochód (ok. 10 min, 500 g CO₂)."


def test_zero_emission_above_threshold_loses():
    results = [R(Mode.BIKE, 20), R(Mode.CAR, 10, co2=500, cost=4)]
    assert recommend(GOOD, results).mode is Mode.CAR


def test_faster_of_walk_and_bike_is_compared():
    results = [R(Mode.WALK, 14), R(Mode.BIKE, 12), R(Mode.CAR, 10, co2=500, cost=4)]
    assert recommend(GOOD, results).mode is Mode.BIKE


def test_walk_considered_when_bike_is_too_slow_vs_threshold_but_walk_is_not():
    results = [R(Mode.WALK, 13), R(Mode.BIKE, 13.5), R(Mode.CAR, 10, co2=500, cost=4)]
    assert recommend(GOOD, results).mode is Mode.WALK


def test_rain_no_zero_emission_option_fastest_wins():
    rec = recommend(RAIN, GREEN_TRIP)
    assert rec.mode is Mode.CAR
    assert "zamiast" not in rec.reason


def test_frost_only_walking_is_compared():
    rec = recommend(COLD, GREEN_TRIP)  # bike dropped; walk 29 min < 19.5 x 1.5 = 29.25
    assert rec.mode is Mode.WALK
    assert rec.reason == (
        "Rower odpada (mróz -3 °C). "
        "Pieszo (ok. 29 min) zamiast samochodu (ok. 20 min): o 9 min dłużej, ale oszczędzasz 7,59 zł i 1104 g CO₂."
    )


def test_time_limit_still_applies_before_threshold():
    # bike 58 min < car 40 x 1.5 = 60, but over MAX_BIKE_MINUTES (40) -> dropped
    results = [R(Mode.BIKE, 58), R(Mode.CAR, 40, co2=2000, cost=12)]
    rec = recommend(GOOD, results)
    assert rec.mode is Mode.CAR
    assert rec.reason.startswith("Rower odpada (ok. 58 min, za długo).")


def test_compared_against_public_transport_when_it_is_fastest():
    results = [R(Mode.BIKE, 30), R(Mode.CAR, 28, co2=1500, cost=10), R(Mode.PUBLIC_TRANSPORT, 25, co2=700, cost=6)]
    rec = recommend(GOOD, results)
    assert rec.mode is Mode.BIKE
    assert rec.reason == (
        "Rower (ok. 30 min) zamiast komunikacji miejskiej (ok. 25 min): "
        "o 5 min dłużej, ale oszczędzasz 6,00 zł i 700 g CO₂."
    )


def test_threshold_comes_from_config(monkeypatch):
    results = [R(Mode.BIKE, 18), R(Mode.CAR, 10, co2=500, cost=4)]
    assert recommend(GOOD, results).mode is Mode.CAR
    monkeypatch.setattr(config, "ZERO_EMISSION_MAX_EXTRA_TIME_RATIO", 1.0)  # +100%
    assert recommend(GOOD, results).mode is Mode.BIKE


def test_no_weather_still_prefers_zero_emission():
    rec = recommend(None, GREEN_TRIP)
    assert rec.mode is Mode.BIKE
    assert rec.reason.startswith("Brak danych pogodowych, pogoda nie została uwzględniona. Rower (ok. 24 min) zamiast")


# --- zero_emission_alternative ---

def test_zero_emission_alternative_none_when_fastest_is_green():
    fastest = R(Mode.BIKE, 9)
    assert zero_emission_alternative(fastest, [fastest, R(Mode.CAR, 10, co2=1)]) is None


def test_zero_emission_alternative_none_without_green_candidates():
    fastest = R(Mode.CAR, 10, co2=500)
    assert zero_emission_alternative(fastest, [fastest, R(Mode.PUBLIC_TRANSPORT, 12, co2=300)]) is None


def test_zero_emission_alternative_returns_faster_green():
    fastest = R(Mode.CAR, 10, co2=500)
    walk, bike = R(Mode.WALK, 14), R(Mode.BIKE, 11)
    assert zero_emission_alternative(fastest, [walk, bike, fastest]) is bike


# --- helpers ---

@pytest.mark.parametrize(("value", "text"), [(7.59, "7,59"), (6, "6,00"), (0.005, "0,01"), (12.3, "12,30")])
def test_format_pln(value, text):
    assert format_pln(value) == text


def test_zero_emission_modes():
    assert ZERO_EMISSION_MODES == {Mode.WALK, Mode.BIKE}


def test_every_non_zero_emission_mode_has_genitive_label():
    assert set(MODE_LABELS_PL_GENITIVE) == set(Mode) - ZERO_EMISSION_MODES


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


# --- no weather data ---

def test_no_weather_skips_weather_rules_and_says_so():
    rec = recommend(None, SHORT_TRIP)
    assert rec.mode is Mode.BIKE
    assert rec.reason == (
        "Brak danych pogodowych, pogoda nie została uwzględniona. Najszybciej: rower (ok. 9 min, 0 g CO₂)."
    )


def test_no_weather_still_applies_time_limits():
    rec = recommend(None, LONG_TRIP)
    assert rec.mode is Mode.CAR
    assert "pieszo odpada (ok. 120 min, za długo)" in rec.reason
