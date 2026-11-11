from datetime import datetime, timedelta, timezone

from sqlalchemy import inspect
from sqlmodel import Session

from app import db
from app.models import Trip, utc_now


def test_utc_now_is_timezone_aware_utc():
    now = utc_now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)
    assert abs(datetime.now(timezone.utc) - now) < timedelta(seconds=5)


def test_trip_table_is_created(tmp_path):
    engine = db.make_engine(f"sqlite:///{tmp_path / 't.db'}")
    db.create_db_and_tables(engine)

    columns = {c["name"]: c for c in inspect(engine).get_columns("trip")}
    assert set(columns) == {
        "id", "name", "origin", "destination", "notes",
        "origin_lat", "origin_lon", "destination_lat", "destination_lon", "created_at",
    }
    for nullable in ("notes", "origin_lat", "origin_lon", "destination_lat", "destination_lon"):
        assert columns[nullable]["nullable"] is True
    for required in ("name", "origin", "destination", "created_at"):
        assert columns[required]["nullable"] is False


def test_trip_saves_with_defaults(tmp_path):
    engine = db.make_engine(f"sqlite:///{tmp_path / 't.db'}")
    db.create_db_and_tables(engine)

    with Session(engine) as session:
        trip = Trip(name="Work", origin="Kraków", destination="Wieliczka")
        session.add(trip)
        session.commit()
        session.refresh(trip)

    assert trip.id is not None
    assert trip.notes is None
    assert trip.origin_lat is None and trip.destination_lon is None
    assert isinstance(trip.created_at, datetime)
