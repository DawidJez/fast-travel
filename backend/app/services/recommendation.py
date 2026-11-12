"""Weather-aware recommendation: pure function, no I/O.

Rule (fastest first):
1. Weather: rain or strong wind drops walking and cycling; frost drops cycling only (ice).
2. Time limits: walking over MAX_WALK_MINUTES or cycling over MAX_BIKE_MINUTES is dropped.
3. From the rest pick the fastest (whole minutes, what the user sees); a tie goes to lower
   CO2, then lower cost.
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


def recommend(weather: Weather, results: list[ModeResult]) -> Recommendation:
    """Pick the recommended mode with a short Polish reason.

    Raises ValueError if `results` is empty or no mode survives the weather and time rules.
    """
    if not results:
        raise ValueError("results must not be empty")

    excluded = weather_exclusions(weather)
    notes = []
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
    return Recommendation(mode=best.mode, reason=reason)
