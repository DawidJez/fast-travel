from sqlalchemy import inspect, text
from sqlmodel import Field, Session, SQLModel

from app import db


class _DbTestItem(SQLModel, table=True):
    __tablename__ = "_db_test_item"
    id: int | None = Field(default=None, primary_key=True)


def test_make_engine_connects_to_sqlite():
    engine = db.make_engine("sqlite://")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1
    assert engine.dialect.name == "sqlite"


def test_create_db_and_tables_creates_registered_tables(empty_engine):
    assert inspect(empty_engine).get_table_names() == []
    db.create_db_and_tables(empty_engine)
    assert "_db_test_item" in inspect(empty_engine).get_table_names()


def test_create_db_and_tables_uses_module_engine_by_default(empty_engine, monkeypatch):
    monkeypatch.setattr(db, "engine", empty_engine)
    db.create_db_and_tables()
    assert "_db_test_item" in inspect(empty_engine).get_table_names()


def test_get_session_yields_working_session_and_closes(empty_engine, monkeypatch):
    monkeypatch.setattr(db, "engine", empty_engine)

    gen = db.get_session()
    session = next(gen)
    assert isinstance(session, Session)
    assert session.get_bind() is empty_engine
    assert session.exec(text("SELECT 1")).scalar() == 1

    gen.close()
    assert not session.in_transaction()
