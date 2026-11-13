"""Trip comparison: stored trip -> distance -> per-mode figures -> weather -> recommendation.

Read-only: uses the coordinates saved with the trip and writes nothing to the database.
Orchestration only; every number comes from the pure calculator/distance functions.
"""

from collections.abc import Callable
from datetime import datetime

from sqlmodel import Session

from app.schemas import ModeComparisonRead, RecommendationRead, TripComparisonRead, WeatherRead
from app.services import trips as trip_service
from app.services.calculators import (
    Mode,
    ModeResult,
    co2_grams,
    cost_pln,
    is_car_peak,
    travel_time_minutes,
)
from app.services.distance import haversine_km, route_distance_km
from app.services.geo import Coordinates
from app.services.recommendation import recommend
from app.services.weather import Weather, WeatherUnavailableError

# Coordinates -> weather now; app.services.weather.current_weather in production, a fake in tests.
WeatherProvider = Callable[[Coordinates], Weather]

# Modes whose figures are only a rough estimate, with the note shown in the API response.
ESTIMATE_NOTES = {
    Mode.PUBLIC_TRANSPORT: (
        "Szacunek na podstawie średniej prędkości autobusu/tramwaju, "
        "bez rozkładów jazdy i kolei (np. SKM)."
    ),
}


def compare_trip(
    session: Session,
    trip_id: int,
    weather_provider: WeatherProvider,
    now: datetime,
) -> TripComparisonRead:
    """Full comparison for one trip (read-only).

    Raises TripNotFoundError for a missing trip. A weather failure is not an error:
    weather is null and the recommendation ignores it.
    """
    trip = trip_service.get_trip(session, trip_id)

    origin = Coordinates(lat=trip.origin_lat, lon=trip.origin_lon)
    destination = Coordinates(lat=trip.destination_lat, lon=trip.destination_lon)
    straight_km = haversine_km(origin, destination)
    peak = is_car_peak(now)

    rows = []
    results = []
    for mode in Mode:
        km = route_distance_km(mode, straight_km)
        result = ModeResult(
            mode=mode,
            time_minutes=travel_time_minutes(mode, km, peak),
            cost_pln=cost_pln(mode, km),
            co2_grams=co2_grams(mode, km, peak),
        )
        results.append(result)
        rows.append(
            ModeComparisonRead(
                mode=mode,
                distance_km=round(km, 1),
                time_minutes=round(result.time_minutes, 1),
                cost_pln=round(result.cost_pln, 2),
                co2_grams=round(result.co2_grams),
                estimate=mode in ESTIMATE_NOTES,
                note=ESTIMATE_NOTES.get(mode),
            )
        )

    try:
        weather = weather_provider(origin)
    except WeatherUnavailableError:
        weather = None

    recommendation = recommend(weather, results)
    return TripComparisonRead(
        trip_id=trip.id,
        origin=trip.origin,
        destination=trip.destination,
        straight_line_km=round(straight_km, 1),
        car_peak=peak,
        weather=WeatherRead(**weather.model_dump()) if weather is not None else None,
        modes=rows,
        recommendation=RecommendationRead(mode=recommendation.mode, reason=recommendation.reason),
    )
