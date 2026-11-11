"""Database engine, table creation and the per-request session dependency."""

from collections.abc import Iterator

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app import config


def make_engine(database_url: str) -> Engine:
    """Create a SQLite engine usable from FastAPI's worker threads."""
    return create_engine(database_url, connect_args={"check_same_thread": False})


engine = make_engine(config.DATABASE_URL)


def create_db_and_tables(bind: Engine | None = None) -> None:
    """Create all tables for models registered on SQLModel.metadata.

    Model modules must be imported before this is called, otherwise their tables are not known.
    """
    SQLModel.metadata.create_all(bind or engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yield a session and close it after the request."""
    with Session(engine) as session:
        yield session
