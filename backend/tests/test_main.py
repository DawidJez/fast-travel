import asyncio
import json

import pytest
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app import config, main
from app.services.geo import GeocodingUnavailableError, PlaceNotFoundError
from app.services.trips import TripNotFoundError

FRONTEND_ORIGIN = config.DEFAULT_CORS_ORIGINS[0]


def test_lifespan_creates_tables_on_startup(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "create_db_and_tables", lambda: calls.append(True))

    with TestClient(main.app):
        assert calls == [True]


def test_main_registers_trip_table_before_startup():
    assert "trip" in SQLModel.metadata.tables


def test_trip_not_found_handler_returns_404():
    response = asyncio.run(main.trip_not_found_handler(None, TripNotFoundError(5)))
    assert response.status_code == 404
    assert json.loads(response.body) == {"detail": "Trip 5 not found"}


def test_trips_router_is_mounted():
    paths = main.app.openapi()["paths"]
    assert set(paths["/api/trips"]) == {"get", "post"}
    assert set(paths["/api/trips/{trip_id}"]) == {"get", "put", "delete"}


def test_health_returns_ok():
    response = TestClient(main.app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- json_safe / validation handler ---

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (float("nan"), "nan"),
        (float("inf"), "inf"),
        (float("-inf"), "-inf"),
        (1.5, 1.5),
        ("text", "text"),
        (None, None),
        ({"a": [1, float("nan"), {"b": float("inf")}]}, {"a": [1, "nan", {"b": "inf"}]}),
        ((1, float("nan")), [1, "nan"]),
    ],
)
def test_json_safe(value, expected):
    assert main.json_safe(value) == expected


def test_validation_error_handler_returns_422_with_safe_body():
    exc = RequestValidationError([{"type": "finite_number", "loc": ("body", "origin_lat"), "input": float("nan")}])
    response = asyncio.run(main.validation_error_handler(None, exc))
    assert response.status_code == 422
    assert json.loads(response.body) == {
        "detail": [{"type": "finite_number", "loc": ["body", "origin_lat"], "input": "nan"}]
    }


# --- CORS ---

def _preflight(client: TestClient, origin: str):
    return client.options(
        "/api/trips/1",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "content-type",
        },
    )


def test_cors_preflight_allows_frontend_origin():
    response = _preflight(TestClient(main.app), FRONTEND_ORIGIN)

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONTEND_ORIGIN
    assert "DELETE" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()


def test_cors_simple_request_allows_frontend_origin():
    response = TestClient(main.app).get("/api/health", headers={"Origin": FRONTEND_ORIGIN})

    assert response.headers["access-control-allow-origin"] == FRONTEND_ORIGIN


def test_cors_rejects_unknown_origin():
    client = TestClient(main.app)

    preflight = _preflight(client, "http://evil.example")
    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers

    simple = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in simple.headers


# --- geocoding error handlers ---

def test_place_not_found_handler_returns_422():
    response = asyncio.run(main.place_not_found_handler(None, PlaceNotFoundError("Atlantyda")))
    assert response.status_code == 422
    assert json.loads(response.body) == {"detail": "Place not found: 'Atlantyda'"}


def test_geocoding_unavailable_handler_returns_503():
    response = asyncio.run(main.geocoding_unavailable_handler(None, GeocodingUnavailableError("down")))
    assert response.status_code == 503
    assert json.loads(response.body) == {"detail": "down"}
