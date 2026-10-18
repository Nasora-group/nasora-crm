import os
from datetime import timedelta

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _env_int(name: str, default: int) -> int:
    """Entier lu dans l'environnement ; valeur par défaut si absent ou invalide."""
    try:
        return max(0, int(os.environ.get(name, "").strip()))
    except ValueError:
        return default


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
    # Cache applicatif. Il porte aussi les compteurs anti-brute-force
    # (app/login_security.py), qui doivent être partagés entre les workers.
    # SimpleCache (mémoire du processus) reste le défaut en développement/test ;
    # la production utilise Redis (CACHE_REDIS_URL) ou, à défaut, un cache fichier.
    CACHE_REDIS_URL = os.environ.get("CACHE_REDIS_URL", "").strip() or None
    CACHE_TYPE = "RedisCache" if CACHE_REDIS_URL else "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 300

    # Nombre de proxys de confiance devant l'application (ProxyFix, en-tête
    # X-Forwarded-For). 0 = aucun : l'en-tête est ignoré.
    TRUSTED_PROXY_COUNT = 0
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
    # Cache partagé entre les workers gunicorn (voir app/login_security.py).
    # Le dossier CACHE_DIR est fixé dans create_app() (instance/cache).
    CACHE_TYPE = "RedisCache" if BaseConfig.CACHE_REDIS_URL else "FileSystemCache"
    # Render place un proxy devant l'application : 1 par défaut. À ajuster avec
    # TRUSTED_PROXY_COUNT si l'hébergeur ajoute d'autres couches (CDN...).
    TRUSTED_PROXY_COUNT = _env_int("TRUSTED_PROXY_COUNT", 1)
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    CACHE_REDIS_URL = None
    CACHE_TYPE = "SimpleCache"
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
