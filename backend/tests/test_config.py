from pathlib import Path

from app import config


def test_load_db_path_default_when_env_missing():
    assert config.load_db_path({}) == config.DEFAULT_DB_PATH


def test_load_db_path_default_when_env_blank():
    assert config.load_db_path({config.DB_PATH_ENV: "  "}) == config.DEFAULT_DB_PATH


def test_load_db_path_from_env():
    assert config.load_db_path({config.DB_PATH_ENV: "/data/x.db"}) == Path("/data/x.db")


def test_default_db_path_is_inside_backend_dir():
    assert config.DEFAULT_DB_PATH.parent == config.BACKEND_DIR
    assert (config.BACKEND_DIR / "app" / "config.py").is_file()


def test_load_cors_origins_default_when_env_missing():
    assert config.load_cors_origins({}) == ["http://localhost:5173"]


def test_load_cors_origins_default_is_a_copy():
    origins = config.load_cors_origins({})
    origins.append("http://evil.example")
    assert config.DEFAULT_CORS_ORIGINS == ["http://localhost:5173"]


def test_load_cors_origins_splits_and_strips():
    env = {config.CORS_ORIGINS_ENV: " http://a.test , http://b.test ,, "}
    assert config.load_cors_origins(env) == ["http://a.test", "http://b.test"]


def test_load_cors_origins_default_when_env_only_separators():
    assert config.load_cors_origins({config.CORS_ORIGINS_ENV: " , ,"}) == ["http://localhost:5173"]
