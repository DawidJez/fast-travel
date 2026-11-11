from sqlalchemy import inspect, text
from sqlmodel import Field, Session, SQLModel

from app import db


class _DbTestItem(SQLModel, table=True):
    __tablename__ = "_db_test_item"
    id: int | None = Field(default=None, primary_key=True)


def test_make_engine_connects_to_sqlite(tmp_path):
    engine = db.make_engine(f"sqlite:///{tmp_path / 't.db'}")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1
    assert engine.dialect.name == "sqlite"


def test_create_db_and_tables_creates_registered_tables(tmp_path):
    engine = db.make_engine(f"sqlite:///{tmp_path / 't.db'}")
    db.create_db_and_tables(engine)
    assert "_db_test_item" in inspect(engine).get_table_names()


def test_create_db_and_tables_uses_module_engine_by_default(tmp_path, monkeypatch):
    engine = db.make_engine(f"sqlite:///{tmp_path / 't.db'}")
    monkeypatch.setattr(db, "engine", engine)
    db.create_db_and_tables()
    assert "_db_test_item" in inspect(engine).get_table_names()


def test_get_session_yields_working_session_and_closes(tmp_path, monkeypatch):
    engine = db.make_engine(f"sqlite:///{tmp_path / 't.db'}")
    monkeypatch.setattr(db, "engine", engine)

    gen = db.get_session()
    session = next(gen)
    assert isinstance(session, Session)
    assert session.get_bind() is engine
    assert session.exec(text("SELECT 1")).scalar() == 1

    gen.close()
    assert not session.in_transaction()
