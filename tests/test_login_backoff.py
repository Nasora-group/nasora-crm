"""Anti-brute-force : couple (IP, identifiant), délai croissant, IP fiable, cache partagé."""
import pytest
from werkzeug.security import generate_password_hash

from app import create_app, login_security
from app.config import ProductionConfig, TestingConfig
from app.extensions import cache, db
from app.models import User

IP_A = {"REMOTE_ADDR": "10.0.0.1"}
IP_B = {"REMOTE_ADDR": "10.0.0.2"}


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY="backoff-test")
    with app.app_context():
        db.create_all()
        db.session.add_all([
            User(username=name, password=generate_password_hash("correct-password"),
                 role="commercial", project="nasmedic", is_active_account=True)
            for name in ("alice", "bob", "carol")
        ])
        db.session.commit()
        cache.clear()
        yield app
        db.session.remove()
        db.drop_all()


def _login(app, username, password, ip=IP_A):
    return app.test_client().post(
        "/login", data={"username": username, "password": password}, environ_overrides=ip
    )


def _fail(app, username, times, ip=IP_A):
    for _ in range(times):
        _login(app, username, "wrong", ip)


def test_failures_from_one_ip_do_not_lock_the_account_for_others(app):
    _fail(app, "alice", 5, IP_A)
    assert b"Trop de tentatives" in _login(app, "alice", "correct-password", IP_A).data

    # Un autre poste peut toujours se connecter : le compte n'est pas verrouillé.
    response = _login(app, "alice", "correct-password", IP_B)
    assert response.status_code == 302


def test_lockout_doubles_after_each_extra_failure(app, monkeypatch):
    clock = {"now": 1_000_000.0}
    monkeypatch.setattr(login_security, "_now", lambda: clock["now"])

    with app.test_request_context("/login", environ_overrides=IP_A):
        for _ in range(login_security.FAILED_LIMIT):
            login_security.record_failure("alice")
        assert login_security.is_blocked("alice")
        assert login_security.retry_after("alice") == login_security.BACKOFF_BASE_SECONDS

        clock["now"] += login_security.BACKOFF_BASE_SECONDS + 1
        assert not login_security.is_blocked("alice")
        login_security.record_failure("alice")
        assert login_security.retry_after("alice") == 2 * login_security.BACKOFF_BASE_SECONDS

        clock["now"] += 2 * login_security.BACKOFF_BASE_SECONDS + 1
        login_security.record_failure("alice")
        assert login_security.retry_after("alice") == 4 * login_security.BACKOFF_BASE_SECONDS


def test_lockout_is_capped(app, monkeypatch):
    monkeypatch.setattr(login_security, "_now", lambda: 1_000_000.0)
    with app.test_request_context("/login", environ_overrides=IP_A):
        for _ in range(login_security.FAILED_LIMIT + 12):
            login_security.record_failure("alice")
        # 30 s * 2**12 dépasserait largement le plafond.
        assert login_security.retry_after("alice") == login_security.MAX_LOCKOUT_SECONDS


def test_ip_limit_blocks_password_spraying(app, monkeypatch):
    monkeypatch.setattr(login_security, "IP_LIMIT", 6)
    for name in ("alice", "bob", "carol"):
        _fail(app, name, 2, IP_A)  # 2 échecs par compte : sous le seuil par couple
    # Six échecs au total depuis cette IP : elle est bloquée même pour un compte neuf.
    assert b"Trop de tentatives" in _login(app, "alice", "correct-password", IP_A).data
    # Une autre IP n'est pas touchée.
    assert _login(app, "bob", "correct-password", IP_B).status_code == 302


def test_success_clears_pair_counter_but_not_ip_counter(app):
    _fail(app, "alice", 3, IP_A)
    assert _login(app, "alice", "correct-password", IP_A).status_code == 302
    with app.test_request_context("/login", environ_overrides=IP_A):
        pair_state = login_security._get_state(login_security._pair_key("alice"))
        ip_state = login_security._get_state(login_security._ip_key())
    assert pair_state is None
    assert ip_state and ip_state["count"] == 3


def test_username_matching_is_case_insensitive(app):
    _fail(app, "ALICE", 5, IP_A)
    assert b"Trop de tentatives" in _login(app, "alice", "correct-password", IP_A).data


def test_client_ip_uses_cloudflare_header_only_in_production(app):
    from app import login_security

    with app.test_request_context(
        "/login",
        headers={"CF-Connecting-IP": "203.0.113.12", "X-Forwarded-For": "6.6.6.6"},
        environ_overrides=IP_A,
    ):
        app.config["IS_PRODUCTION"] = True
        assert login_security.client_ip() == "203.0.113.12"
        app.config["IS_PRODUCTION"] = False
        assert login_security.client_ip() == "10.0.0.1"


def test_client_ip_ignores_invalid_cloudflare_header(app):
    from app import login_security

    with app.test_request_context(
        "/login", headers={"CF-Connecting-IP": "not-an-ip"}, environ_overrides=IP_A
    ):
        app.config["IS_PRODUCTION"] = True
        assert login_security.client_ip() == "10.0.0.1"


def test_client_ip_uses_true_client_ip_when_cloudflare_header_is_missing(app):
    with app.test_request_context(
        "/login",
        headers={"True-Client-IP": "203.0.113.25", "X-Forwarded-For": "6.6.6.6"},
        environ_overrides=IP_A,
    ):
        app.config["IS_PRODUCTION"] = True
        assert login_security.client_ip() == "203.0.113.25"


def test_client_ip_falls_back_to_true_client_ip_when_cloudflare_value_is_invalid(app):
    with app.test_request_context(
        "/login",
        headers={
            "CF-Connecting-IP": "not-an-ip",
            "True-Client-IP": "203.0.113.26",
            "X-Forwarded-For": "6.6.6.6",
        },
        environ_overrides=IP_A,
    ):
        app.config["IS_PRODUCTION"] = True
        assert login_security.client_ip() == "203.0.113.26"


def test_production_uses_a_cache_shared_between_workers():
    assert ProductionConfig.CACHE_TYPE in {"FileSystemCache", "RedisCache"}
    assert ProductionConfig.CACHE_TYPE != "SimpleCache"
    assert ProductionConfig.IS_PRODUCTION is True


def test_file_cache_shares_counters_between_app_instances(tmp_path):
    """Deux 'workers' (deux apps) voient les mêmes compteurs."""

    class SharedFileCache(TestingConfig):
        CACHE_TYPE = "FileSystemCache"
        CACHE_DIR = str(tmp_path / "cache")

    worker_1 = create_app(SharedFileCache)
    with worker_1.test_request_context("/login", environ_overrides=IP_A):
        for _ in range(login_security.FAILED_LIMIT):
            login_security.record_failure("alice")

    worker_2 = create_app(SharedFileCache)
    with worker_2.test_request_context("/login", environ_overrides=IP_A):
        assert login_security.is_blocked("alice")
