import pytest
from flask import session
from werkzeug.security import generate_password_hash

from app.config import TestingConfig
from app import create_app
from app.extensions import db
from app.models import User
from app.login_security import clear_failures


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY="login-security-test")
    with app.app_context():
        db.create_all()
        user = User(
            username="security_test",
            password=generate_password_hash("correct-password"),
            role="commercial",
            project="nasmedic",
            is_active_account=True,
        )
        disabled = User(
            username="disabled_test",
            password=generate_password_hash("correct-password"),
            role="commercial",
            project="nasmedic",
            is_active_account=False,
        )
        db.session.add_all([user, disabled])
        db.session.commit()
        clear_failures(user.username)
        clear_failures(disabled.username)
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def test_login_blocks_repeated_failures(client):
    for _ in range(4):
        response = client.post("/login", data={"username": "security_test", "password": "wrong"})
        assert response.status_code == 200

    # The fifth failed attempt reaches the configured threshold.
    response = client.post("/login", data={"username": "security_test", "password": "wrong"})
    assert response.status_code == 200
    assert b"Nom d'utilisateur ou mot de passe incorrect" in response.data

    # The following request is rejected by the temporary lockout.
    response = client.post("/login", data={"username": "security_test", "password": "wrong"})
    assert response.status_code == 200
    assert b"Trop de tentatives de connexion" in response.data

    response = client.post("/login", data={"username": "security_test", "password": "correct-password"})
    assert response.status_code == 200
    assert b"Trop de tentatives de connexion" in response.data


def test_successful_login_clears_failure_counter(client):
    for _ in range(2):
        client.post("/login", data={"username": "security_test", "password": "wrong"})
    response = client.post("/login", data={"username": "security_test", "password": "correct-password"})
    assert response.status_code == 302
    with client.session_transaction() as current_session:
        assert current_session.get("_user_id")


def test_disabled_account_cannot_login(client):
    response = client.post("/login", data={"username": "disabled_test", "password": "correct-password"})
    assert response.status_code == 200
    with client.session_transaction() as current_session:
        assert "_user_id" not in current_session


def test_login_security_does_not_store_password_in_session(client):
    client.post("/login", data={"username": "security_test", "password": "correct-password"})
    with client.session_transaction() as current_session:
        assert "password" not in current_session
        assert "correct-password" not in repr(dict(current_session))
