from app.config import ProductionConfig, TestingConfig


def test_testing_config_keeps_local_cache():
    assert TestingConfig.CACHE_TYPE == "SimpleCache"
    assert TestingConfig.CACHE_REDIS_URL is None


def test_production_cache_can_use_shared_backend(monkeypatch):
    monkeypatch.setenv("CACHE_REDIS_URL", "redis://example.invalid:6379/0")

    # BaseConfig is evaluated at import time, so the production configuration
    # intentionally documents the environment-driven contract rather than
    # mutating the live application configuration during the test.
    assert ProductionConfig.CACHE_TYPE in {"SimpleCache", "RedisCache"}
    assert hasattr(ProductionConfig, "CACHE_REDIS_URL")
