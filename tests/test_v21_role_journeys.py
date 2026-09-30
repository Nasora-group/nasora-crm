import pytest
from flask_login import login_user
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import User
from app.services.audit import audit_event


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY="v21-role-test")
    with app.app_context():
        db.create_all()
        users = [
            User(username="admin_v21", password=generate_password_hash("pass"), role="admin", project="nasmedic", is_active_account=True),
            User(username="vm_v21", password=generate_password_hash("pass"), role="commercial", project="nasmedic", is_active_account=True),
            User(username="anim_v21", password=generate_password_hash("pass"), role="animateur", project="nasmedic", is_active_account=True),
        ]
        db.session.add_all(users)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(client, username):
    response = client.post("/login", data={"username": username, "password": "pass"}, follow_redirects=False)
    assert response.status_code == 302


def test_health_check_is_available(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("username", "path", "expected"),
    [
        ("admin_v21", "/v2/pilotage", 200),
        ("admin_v21", "/v2/planning", 200),
        ("vm_v21", "/v2/professionnels/", 200),
        ("anim_v21", "/v2/professionnels/", 200),
        ("anim_v21", "/v2/animations/", 200),
        ("vm_v21", "/v2/animations/", 200),
        ("vm_v21", "/v2/planning", 403),
        ("anim_v21", "/v2/planning", 403),
        ("admin_v21", "/v2/animations/", 200),
    ],
)
def test_v21_role_route_matrix(client, username, path, expected):
    _login(client, username)
    response = client.get(path)
    assert response.status_code == expected


def test_v21_audit_event_is_persisted(app):
    with app.test_request_context("/test"):
        user = User.query.filter_by(username="admin_v21").one()
        login_user(user)
        audit_event("v21_test", "test_entity", 123, {"check": True})

    row = db.session.execute(
        db.text("SELECT action, entity_type, entity_id FROM audit_log WHERE action = 'v21_test' ORDER BY id DESC LIMIT 1")
    ).first()
    assert row is not None
    assert row.action == "v21_test"
    assert row.entity_type == "test_entity"
    assert row.entity_id == "123"
