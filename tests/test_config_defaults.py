import pytest

from app import create_app
from app.config import DevelopmentConfig, ProductionConfig, TestingConfig, get_config


def test_missing_flask_env_defaults_to_production(monkeypatch):
    monkeypatch.delenv("FLASK_ENV", raising=False)
    assert get_config() is ProductionConfig


@pytest.mark.parametrize("value", ["", "  ", "prod", "devel", "staging"])
def test_unknown_or_empty_flask_env_defaults_to_production(monkeypatch, value):
    monkeypatch.setenv("FLASK_ENV", value)
    assert get_config() is ProductionConfig


@pytest.mark.parametrize(
    "value, expected",
    [
        ("development", DevelopmentConfig),
        ("Development", DevelopmentConfig),
        ("production", ProductionConfig),
        ("testing", TestingConfig),
    ],
)
def test_explicit_flask_env_is_respected(monkeypatch, value, expected):
    monkeypatch.setenv("FLASK_ENV", value)
    assert get_config() is expected


def test_only_production_config_is_flagged_production():
    assert ProductionConfig.IS_PRODUCTION is True
    assert DevelopmentConfig.IS_PRODUCTION is False
    assert TestingConfig.IS_PRODUCTION is False
    assert ProductionConfig.DEBUG is False


def test_production_refuses_to_start_without_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(ProductionConfig)


def test_production_refuses_to_start_without_database_url(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_app(ProductionConfig)


def test_production_enables_hsts_and_https_redirect(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    app = create_app(ProductionConfig)
    assert app.debug is False
    client = app.test_client()

    secure = client.get("/", headers={"X-Forwarded-Proto": "https"})
    assert "max-age=31536000" in secure.headers["Strict-Transport-Security"]

    insecure = client.get("/", headers={"X-Forwarded-Proto": "http"})
    assert insecure.status_code == 308
    assert insecure.headers["Location"].startswith("https://")


def test_testing_config_does_not_force_https_or_hsts():
    app = create_app(TestingConfig)
    response = app.test_client().get("/", headers={"X-Forwarded-Proto": "http"})
    assert response.status_code == 200
    assert "Strict-Transport-Security" not in response.headers
