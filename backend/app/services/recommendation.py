"""Weather-aware recommendation: pure function, no I/O.

Rule:
1. Weather: rain or strong wind drops walking and cycling; frost drops cycling only (ice).
2. Time limits: walking over MAX_WALK_MINUTES or cycling over MAX_BIKE_MINUTES is dropped.
3. From the rest find the fastest (whole minutes, what the user sees); a tie goes to lower
   CO2, then lower cost.
4. If the fastest is not zero-emission, but the faster remaining zero-emission mode (walk/bike)
   takes less than fastest x (1 + ZERO_EMISSION_MAX_EXTRA_TIME_RATIO), recommend that one and
   say how much time it costs and how much PLN and CO2 it saves. Otherwise the fastest wins.
"""

from dataclasses import dataclass

from app import config
from app.services.calculators import Mode, ModeResult
from app.services.weather import Weather

MODE_LABELS_PL = {
    Mode.WALK: "pieszo",
    Mode.BIKE: "rower",
    Mode.CAR: "samochód",
    Mode.PUBLIC_TRANSPORT: "komunikacja miejska",
}

# Genitive forms for "... zamiast samochodu" (only modes that can be the faster alternative).
MODE_LABELS_PL_GENITIVE = {
    Mode.CAR: "samochodu",
    Mode.PUBLIC_TRANSPORT: "komunikacji miejskiej",
}

ZERO_EMISSION_MODES = frozenset({Mode.WALK, Mode.BIKE})


@dataclass(frozen=True)
class Recommendation:
    mode: Mode
    reason: str


def weather_exclusions(weather: Weather) -> dict[Mode, list[str]]:
    """Modes to drop because of the weather, each with Polish reasons; empty if all is fine."""
    excluded: dict[Mode, list[str]] = {}

    def drop(modes: tuple[Mode, ...], reason: str) -> None:
        for mode in modes:
            excluded.setdefault(mode, []).append(reason)

    if weather.precipitation_mm >= config.RAIN_THRESHOLD_MM:
        drop((Mode.WALK, Mode.BIKE), f"opady {weather.precipitation_mm:g} mm")
    if weather.wind_speed_kmh >= config.STRONG_WIND_THRESHOLD_KMH:
        drop((Mode.WALK, Mode.BIKE), f"silny wiatr {weather.wind_speed_kmh:g} km/h")
    if weather.temperature_c < config.FROST_THRESHOLD_C:
        drop((Mode.BIKE,), f"mróz {weather.temperature_c:g} °C")
    return excluded


def too_long(result: ModeResult) -> bool:
    """Walking / cycling slower than the acceptable time limit."""
    limit = {Mode.WALK: config.MAX_WALK_MINUTES, Mode.BIKE: config.MAX_BIKE_MINUTES}.get(result.mode)
    return limit is not None and result.time_minutes > limit


def _rank_key(result: ModeResult) -> tuple[int, float, float]:
    return (round(result.time_minutes), result.co2_grams, result.cost_pln)


def format_pln(value: float) -> str:
    """Polish money format: two decimals with a decimal comma, e.g. 7,59."""
    return f"{value:.2f}".replace(".", ",")


def zero_emission_alternative(fastest: ModeResult, candidates: list[ModeResult]) -> ModeResult | None:
    """The faster remaining walk/bike option if it is less than ZERO_EMISSION_MAX_EXTRA_TIME_RATIO
    slower than `fastest` (exact times); None if `fastest` is already zero-emission or none qualifies."""
    if fastest.mode in ZERO_EMISSION_MODES:
        return None
    green = [r for r in candidates if r.mode in ZERO_EMISSION_MODES]
    if not green:
        return None
    best_green = min(green, key=_rank_key)
    limit = fastest.time_minutes * (1 + config.ZERO_EMISSION_MAX_EXTRA_TIME_RATIO)
    return best_green if best_green.time_minutes < limit else None


def _zero_emission_reason(chosen: ModeResult, fastest: ModeResult) -> str:
    chosen_min, fastest_min = round(chosen.time_minutes), round(fastest.time_minutes)
    label = MODE_LABELS_PL[chosen.mode]
    return (
        f"{label[0].upper() + label[1:]} (ok. {chosen_min} min) zamiast "
        f"{MODE_LABELS_PL_GENITIVE[fastest.mode]} (ok. {fastest_min} min): "
        f"o {chosen_min - fastest_min} min dłużej, ale oszczędzasz "
        f"{format_pln(fastest.cost_pln - chosen.cost_pln)} zł i "
        f"{round(fastest.co2_grams - chosen.co2_grams)} g CO₂."
    )


def recommend(weather: Weather | None, results: list[ModeResult]) -> Recommendation:
    """Pick the recommended mode with a short Polish reason.

    `weather=None` (service unavailable): no weather rules, and the reason says so.
    Raises ValueError if `results` is empty or no mode survives the weather and time rules.
    """
    if not results:
        raise ValueError("results must not be empty")

    excluded = weather_exclusions(weather) if weather is not None else {}
    notes = [] if weather is not None else ["brak danych pogodowych, pogoda nie została uwzględniona"]
    candidates = []
    for r in results:
        label = MODE_LABELS_PL[r.mode]
        if r.mode in excluded:
            notes.append(f"{label} odpada ({', '.join(excluded[r.mode])})")
        elif too_long(r):
            notes.append(f"{label} odpada (ok. {round(r.time_minutes)} min, za długo)")
        else:
            candidates.append(r)
    if not candidates:
        raise ValueError("no mode left after applying the weather and time rules")

    best = min(candidates, key=_rank_key)
    green = zero_emission_alternative(best, candidates)

    if green is not None:
        chosen = green
        reason = _zero_emission_reason(green, best)
    else:
        chosen = best
        same_time = [r for r in candidates if round(r.time_minutes) == round(best.time_minutes)]
        reason = (
            f"Najszybciej: {MODE_LABELS_PL[best.mode]} "
            f"(ok. {round(best.time_minutes)} min, {round(best.co2_grams)} g CO₂)"
        )
        if len(same_time) > 1:
            reason += ", przy równym czasie wybrano niższą emisję CO₂"
        reason += "."
    if notes:
        joined = "; ".join(notes)
        reason = joined[0].upper() + joined[1:] + ". " + reason
    return Recommendation(mode=chosen.mode, reason=reason)
