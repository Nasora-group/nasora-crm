import os
from datetime import timedelta

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _normalize_db_url(url: str) -> str:
    """Render/Railway/Heroku fournissent parfois 'postgres://' alors que
    SQLAlchemy 1.4+ exige 'postgresql://'."""
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(
        os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'instance', 'plateforme_commerciale.db')}")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SEND_FILE_MAX_AGE_DEFAULT = 86400
    # Render/PostgreSQL peut fermer une connexion restée inactive. Le contrôle
    # avant utilisation évite de réutiliser une connexion morte et le recyclage
    # limite la durée de vie des connexions persistantes.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 300
    WTF_CSRF_ENABLED = True
    # Vrai uniquement pour ProductionConfig : pilote HTTPS forcé, HSTS et
    # vérification des variables d'environnement obligatoires.
    IS_PRODUCTION = False

    # Session applicative : expiration après 8 h, avec renouvellement pendant
    # l'activité. Les cookies restent inaccessibles au JavaScript et limitent
    # les envois cross-site.
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_REFRESH_EACH_REQUEST = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SECRET_KEY = BaseConfig.SECRET_KEY or "dev-only-insecure-key-do-not-use-in-prod"


class ProductionConfig(BaseConfig):
    DEBUG = False
    IS_PRODUCTION = True
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "testing-key"


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config():
    """Choisit la configuration selon FLASK_ENV.

    Par sécurité, l'absence de FLASK_ENV ou une valeur inconnue (faute de
    frappe) donne la configuration de PRODUCTION. Le mode développement
    (DEBUG, clé secrète de secours) doit être demandé explicitement avec
    FLASK_ENV=development.
    """
    env = (os.environ.get("FLASK_ENV") or "production").strip().lower()
    return config_by_name.get(env, ProductionConfig)
