import pytest

VALID = {"name": "Work", "origin": "Kraków", "destination": "Wieliczka"}


def _post(client, **overrides):
    return client.post("/api/trips", json={**VALID, **overrides})


# --- POST /api/trips ---

def test_create_returns_201_and_trip(client):
    response = _post(client, notes="n", origin_lat=50.06, origin_lon=19.94)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["name"] == "Work"
    assert body["origin_lat"] == 50.06
    assert body["destination_lat"] is None
    assert body["created_at"].endswith(("Z", "+00:00"))


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": "Work", "origin": "Kraków"},
        {**VALID, "name": "   "},
        {**VALID, "name": "x" * 101},
        {**VALID, "origin_lat": 91, "origin_lon": 0},
        {**VALID, "origin_lat": 50.0},
        {**VALID, "name": 123},
    ],
)
def test_create_invalid_input_returns_422(client, payload):
    assert client.post("/api/trips", json=payload).status_code == 422


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
def test_create_non_finite_coordinate_returns_422_not_500(client, bad):
    body = '{"name": "a", "origin": "b", "destination": "c", "origin_lat": %s, "origin_lon": 1}' % bad
    response = client.post("/api/trips", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "origin_lat"]


def test_create_nan_in_text_field_returns_422_not_500(client):
    body = '{"name": "a", "origin": "b", "destination": "c", "notes": NaN}'
    response = client.post("/api/trips", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422


def test_create_rejects_non_json_body(client):
    assert client.post("/api/trips", content="nope", headers={"Content-Type": "text/plain"}).status_code == 422


# --- GET /api/trips ---

def test_list_empty(client):
    response = client.get("/api/trips")
    assert response.status_code == 200
    assert response.json() == []


def test_list_returns_created_trips_newest_first(client):
    _post(client, name="A")
    _post(client, name="B")
    names = [t["name"] for t in client.get("/api/trips").json()]
    assert names == ["B", "A"]


# --- GET /api/trips/{id} ---

def test_get_existing(client):
    trip_id = _post(client).json()["id"]
    response = client.get(f"/api/trips/{trip_id}")
    assert response.status_code == 200
    assert response.json()["id"] == trip_id


def test_get_missing_returns_404(client):
    response = client.get("/api/trips/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Trip 999 not found"}


def test_get_non_integer_id_returns_422(client):
    assert client.get("/api/trips/abc").status_code == 422


# --- PUT /api/trips/{id} ---

def test_update_partial(client):
    trip_id = _post(client, notes="keep").json()["id"]
    response = client.put(f"/api/trips/{trip_id}", json={"name": "Home"})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Home"
    assert body["origin"] == "Kraków"
    assert body["notes"] == "keep"


def test_update_missing_returns_404(client):
    assert client.put("/api/trips/999", json={"name": "X"}).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [{"name": None}, {"name": " "}, {"origin_lat": 50.0}, {"destination_lat": 0, "destination_lon": 181}],
)
def test_update_invalid_input_returns_422(client, payload):
    trip_id = _post(client).json()["id"]
    assert client.put(f"/api/trips/{trip_id}", json=payload).status_code == 422


def test_update_full_coordinate_pair(client):
    trip_id = _post(client).json()["id"]
    response = client.put(f"/api/trips/{trip_id}", json={"destination_lat": 49.98, "destination_lon": 20.06})
    assert response.status_code == 200
    body = response.json()
    assert (body["destination_lat"], body["destination_lon"]) == (49.98, 20.06)
    assert body["origin_lat"] is None


def test_update_renamed_place_clears_its_stale_coordinates(client):
    trip_id = _post(client, origin_lat=50.06, origin_lon=19.94, destination_lat=49.98, destination_lon=20.06).json()["id"]
    body = client.put(f"/api/trips/{trip_id}", json={"origin": "Tarnów"}).json()
    assert body["origin"] == "Tarnów"
    assert body["origin_lat"] is None and body["origin_lon"] is None
    assert (body["destination_lat"], body["destination_lon"]) == (49.98, 20.06)


def test_update_invalid_input_on_missing_trip_returns_422(client):
    assert client.put("/api/trips/999", json={"name": None}).status_code == 422


# --- DELETE /api/trips/{id} ---

def test_delete_returns_204_and_removes(client):
    trip_id = _post(client).json()["id"]
    response = client.delete(f"/api/trips/{trip_id}")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/api/trips/{trip_id}").status_code == 404


def test_delete_missing_returns_404(client):
    assert client.delete("/api/trips/999").status_code == 404


# --- trip id bounds (all /{trip_id} routes) ---

TOO_BIG_ID = str(2**63)  # one past SQLite's max INTEGER


@pytest.mark.parametrize("method", ["get", "put", "delete"])
@pytest.mark.parametrize("bad_id", ["0", "-1", TOO_BIG_ID, "99999999999999999999"])
def test_out_of_range_id_returns_422_not_500(client, method, bad_id):
    kwargs = {"json": {"name": "X"}} if method == "put" else {}
    response = getattr(client, method)(f"/api/trips/{bad_id}", **kwargs)
    assert response.status_code == 422


@pytest.mark.parametrize("method", ["get", "delete"])
def test_max_sqlite_id_is_accepted_and_returns_404(client, method):
    response = getattr(client, method)(f"/api/trips/{2**63 - 1}")
    assert response.status_code == 404
