from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app import db
from app.models import Trip, utc_now

COORDS = {"origin_lat": 50.06, "origin_lon": 19.94, "destination_lat": 49.99, "destination_lon": 20.06}


def test_utc_now_is_timezone_aware_utc():
    now = utc_now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)
    assert abs(datetime.now(timezone.utc) - now) < timedelta(seconds=5)


def test_trip_table_is_created(empty_engine):
    engine = empty_engine
    db.create_db_and_tables(engine)

    columns = {c["name"]: c for c in inspect(engine).get_columns("trip")}
    assert set(columns) == {
        "id", "name", "origin", "destination", "notes",
        "origin_lat", "origin_lon", "destination_lat", "destination_lon", "created_at",
    }
    assert columns["notes"]["nullable"] is True
    for required in ("name", "origin", "destination", "created_at",
                     "origin_lat", "origin_lon", "destination_lat", "destination_lon"):
        assert columns[required]["nullable"] is False, required


def test_trip_saves_with_defaults(engine):
    with Session(engine) as session:
        trip = Trip(name="Work", origin="Kraków", destination="Wieliczka", **COORDS)
        session.add(trip)
        session.commit()
        session.refresh(trip)

    assert trip.id is not None
    assert trip.notes is None
    assert trip.origin_lat == 50.06
    assert isinstance(trip.created_at, datetime)


def test_trip_without_coordinates_is_rejected_by_database(engine):
    with Session(engine) as session:
        session.add(Trip(name="Work", origin="Kraków", destination="Wieliczka"))
        with pytest.raises(IntegrityError):
            session.commit()
