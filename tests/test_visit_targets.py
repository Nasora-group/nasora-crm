import pytest
from sqlalchemy import inspect
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import User


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY="test")
    with app.app_context():
        db.create_all()
        admin = User(username="admin_targets", password=generate_password_hash("password"), role="admin", project="nasmedic", is_active_account=True)
        commercial = User(username="commercial_targets", password=generate_password_hash("password"), role="commercial", project="nasmedic", is_active_account=True)
        db.session.add_all([admin, commercial])
        db.session.commit()
        yield app, admin, commercial
        db.session.remove()
        db.drop_all()


def login(client, username):
    return client.post("/login", data={"username": username, "password": "password"}, follow_redirects=True)


def test_visit_target_persists_and_updates(app):
    flask_app, admin, commercial = app
    client = flask_app.test_client()
    login(client, admin.username)

    response = client.post(f"/admin/visit-objectives/{commercial.id}", data={"target": "120"})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "commercial_id": commercial.id, "target": 120}

    response = client.get("/admin/visit-objectives")
    assert response.status_code == 200
    assert response.get_json()[str(commercial.id)] == 120

    response = client.post(f"/admin/visit-objectives/{commercial.id}", data={"target": "75"})
    assert response.status_code == 200
    assert response.get_json()["target"] == 75

    assert client.get("/admin/visit-objectives").get_json()[str(commercial.id)] == 75


def test_visit_target_validation(app):
    flask_app, admin, commercial = app
    client = flask_app.test_client()
    login(client, admin.username)

    for value in ["-1", "10001", "12.5", "abc"]:
        response = client.post(f"/admin/visit-objectives/{commercial.id}", data={"target": value})
        assert response.status_code == 400
        assert response.get_json()["ok"] is False


def test_visit_target_requires_admin(app):
    flask_app, _admin, commercial = app
    client = flask_app.test_client()
    login(client, commercial.username)

    response = client.post(f"/admin/visit-objectives/{commercial.id}", data={"target": "120"})
    assert response.status_code == 403


def test_visit_target_read_does_not_create_table(app):
    flask_app, admin, _commercial = app
    client = flask_app.test_client()
    login(client, admin.username)

    assert not inspect(db.engine).has_table("visit_objective")

    response = client.get("/admin/visit-objectives")

    assert response.status_code == 200
    assert response.get_json() == {}
    assert not inspect(db.engine).has_table("visit_objective")
