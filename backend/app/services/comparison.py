"""Trip comparison: trip -> coordinates -> distance -> per-mode figures -> weather -> recommendation.

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
    route_distance_km,
    travel_time_minutes,
)
from app.services.distance import haversine_km
from app.services.geo import Coordinates, GeocodingError
from app.services.recommendation import recommend
from app.services.weather import Weather, WeatherUnavailableError

# Coordinates -> weather now; app.services.weather.current_weather in production, a fake in tests.
WeatherProvider = Callable[[Coordinates], Weather]


def ensure_coordinates(session: Session, trip, geocoder: trip_service.Geocoder) -> None:
    """Geocode and save missing coordinates (e.g. trips stored before geocoding-on-save).

    Raises GeocodingError and leaves the stored trip unchanged if geocoding fails.
    """
    if None not in (trip.origin_lat, trip.origin_lon, trip.destination_lat, trip.destination_lon):
        return
    try:
        trip_service.fill_missing_coordinates(trip, geocoder)
    except GeocodingError:
        session.rollback()
        raise
    session.add(trip)
    session.commit()
    session.refresh(trip)


def compare_trip(
    session: Session,
    trip_id: int,
    geocoder: trip_service.Geocoder,
    weather_provider: WeatherProvider,
    now: datetime,
) -> TripComparisonRead:
    """Full comparison for one trip.

    Raises TripNotFoundError (missing trip) and GeocodingError (coordinates cannot be found).
    A weather failure is not an error: weather is null and the recommendation ignores it.
    """
    trip = trip_service.get_trip(session, trip_id)
    ensure_coordinates(session, trip, geocoder)

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
