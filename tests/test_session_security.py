from app.config import ProductionConfig, BaseConfig
from app.extensions import login_manager


def test_base_session_security_defaults():
    assert BaseConfig.SESSION_COOKIE_HTTPONLY is True
    assert BaseConfig.SESSION_COOKIE_SAMESITE == "Lax"
    assert BaseConfig.REMEMBER_COOKIE_HTTPONLY is True
    assert BaseConfig.REMEMBER_COOKIE_SAMESITE == "Lax"
    assert BaseConfig.SESSION_REFRESH_EACH_REQUEST is True
    assert BaseConfig.PERMANENT_SESSION_LIFETIME.total_seconds() == 8 * 60 * 60


def test_production_session_cookies_are_secure():
    assert ProductionConfig.SESSION_COOKIE_SECURE is True
    assert ProductionConfig.REMEMBER_COOKIE_SECURE is True


def test_login_manager_uses_strong_session_protection():
    assert login_manager.session_protection == "strong"
