from fastapi.testclient import TestClient

from app import main


def test_lifespan_creates_tables_on_startup(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "create_db_and_tables", lambda: calls.append(True))

    with TestClient(main.app):
        assert calls == [True]


def test_main_registers_trip_table_before_startup():
    from sqlmodel import SQLModel

    assert "trip" in SQLModel.metadata.tables


def test_trip_not_found_handler_returns_404():
    import asyncio
    import json

    from app.services.trips import TripNotFoundError

    response = asyncio.run(main.trip_not_found_handler(None, TripNotFoundError(5)))
    assert response.status_code == 404
    assert json.loads(response.body) == {"detail": "Trip 5 not found"}


def test_trips_router_is_mounted():
    paths = main.app.openapi()["paths"]
    assert set(paths["/api/trips"]) == {"get", "post"}
    assert set(paths["/api/trips/{trip_id}"]) == {"get", "put", "delete"}


def _preflight(client: TestClient, origin: str):
    return client.options(
        "/docs",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "content-type",
        },
    )


def test_cors_preflight_allows_frontend_origin():
    client = TestClient(main.app)
    response = _preflight(client, "http://localhost:5173")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "DELETE" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()


def test_cors_simple_request_allows_frontend_origin():
    client = TestClient(main.app)
    response = client.get("/openapi.json", headers={"Origin": "http://localhost:5173"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_rejects_unknown_origin():
    client = TestClient(main.app)

    preflight = _preflight(client, "http://evil.example")
    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers

    simple = client.get("/openapi.json", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in simple.headers
