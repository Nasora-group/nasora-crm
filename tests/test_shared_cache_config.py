import importlib

import app.config as config


def test_testing_config_keeps_local_cache():
    assert config.TestingConfig.CACHE_TYPE == "SimpleCache"
    assert config.TestingConfig.CACHE_REDIS_URL is None


def test_production_cache_uses_redis_when_configured(monkeypatch):
    monkeypatch.setenv("CACHE_REDIS_URL", "redis://example.invalid:6379/0")
    importlib.reload(config)
    try:
        assert config.ProductionConfig.CACHE_TYPE == "RedisCache"
        assert config.ProductionConfig.CACHE_REDIS_URL == "redis://example.invalid:6379/0"
    finally:
        monkeypatch.delenv("CACHE_REDIS_URL", raising=False)
        importlib.reload(config)
