import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine
from sqlmodel.pool import StaticPool

from app import db
from app.main import app


@pytest.fixture
def empty_engine():
    """Fresh in-memory SQLite per test, without tables.

    StaticPool keeps one shared connection, so every session (and the TestClient's
    worker thread) sees the same in-memory database instead of a new empty one.
    """
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    yield engine
    engine.dispose()


@pytest.fixture
def engine(empty_engine):
    """Fresh in-memory SQLite per test, with all tables created."""
    db.create_db_and_tables(empty_engine)
    return empty_engine


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(engine):
    """API client using the per-test in-memory database (lifespan not run, so no real DB file)."""

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[db.get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.pop(db.get_session, None)
