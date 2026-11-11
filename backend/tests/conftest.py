import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import db
from app.main import app


@pytest.fixture
def engine(tmp_path):
    """Fresh SQLite file per test, with all tables created."""
    engine = db.make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    db.create_db_and_tables(engine)
    return engine


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(engine):
    """API client using the per-test database (lifespan not run, so no real DB file)."""

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[db.get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()
