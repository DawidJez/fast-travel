import pytest

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
    assert config.load_cors_origins({}) == config.DEFAULT_CORS_ORIGINS


def test_default_cors_origin_is_vite_dev_server():
    assert config.DEFAULT_CORS_ORIGINS == ["http://localhost:5173"]


def test_load_cors_origins_default_is_a_copy():
    before = list(config.DEFAULT_CORS_ORIGINS)
    origins = config.load_cors_origins({})
    origins.append("http://evil.example")
    assert config.DEFAULT_CORS_ORIGINS == before


def test_load_cors_origins_splits_and_strips():
    env = {config.CORS_ORIGINS_ENV: " http://a.test , http://b.test ,, "}
    assert config.load_cors_origins(env) == ["http://a.test", "http://b.test"]


def test_load_cors_origins_default_when_env_only_separators():
    assert config.load_cors_origins({config.CORS_ORIGINS_ENV: " , ,"}) == config.DEFAULT_CORS_ORIGINS


# --- comparison constants: sanity checks (values themselves are sourced in config.py) ---

def test_detour_factor_in_published_range():
    assert 1.1 <= config.DETOUR_FACTOR <= 1.5


def test_earth_radius_is_iugg_mean():
    assert config.EARTH_RADIUS_KM == 6371.0088


def test_speeds_positive_and_ordered():
    speeds = [config.WALK_SPEED_KMH, config.BIKE_SPEED_KMH, config.PUBLIC_TRANSPORT_SPEED_KMH, config.CAR_SPEED_KMH]
    assert all(s > 0 for s in speeds)
    assert speeds == sorted(speeds)  # walk < bike < public transport < car (urban averages)


def test_costs_non_negative():
    for value in (config.CAR_COST_PLN_PER_KM, config.PUBLIC_TRANSPORT_TICKET_PLN,
                  config.BIKE_COST_PLN_PER_KM, config.WALK_COST_PLN_PER_KM):
        assert value >= 0


def test_co2_car_above_public_transport_above_active_modes():
    assert config.CAR_CO2_G_PER_KM > config.PUBLIC_TRANSPORT_CO2_G_PER_KM > 0
    assert config.BIKE_CO2_G_PER_KM == config.WALK_CO2_G_PER_KM == 0



# --- Nominatim switch ---

@pytest.mark.parametrize("value", ["0", "false", "FALSE", " no ", "off"])
def test_load_nominatim_enabled_switched_off(value):
    assert config.load_nominatim_enabled({config.NOMINATIM_ENABLED_ENV: value}) is False


@pytest.mark.parametrize("env", [{}, {config.NOMINATIM_ENABLED_ENV: ""}, {config.NOMINATIM_ENABLED_ENV: "1"},
                                 {config.NOMINATIM_ENABLED_ENV: "true"}])
def test_load_nominatim_enabled_default_on(env):
    assert config.load_nominatim_enabled(env) is True


def test_nominatim_user_agent_is_not_a_library_default():
    assert config.NOMINATIM_USER_AGENT.startswith("fast-travel/")


def test_nominatim_interval_respects_policy_maximum():
    assert config.NOMINATIM_MIN_INTERVAL_SECONDS >= 1.0  # "absolute maximum of 1 request per second"


def test_zero_emission_threshold_is_plus_50_percent():
    assert config.ZERO_EMISSION_MAX_EXTRA_TIME_RATIO == 0.5
