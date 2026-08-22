import pytest

from app import create_app
from app.extensions import db
from app.models import User
from werkzeug.security import generate_password_hash


@pytest.fixture()
def app():
    app = create_app("testing") if False else create_app()
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:", WTF_CSRF_ENABLED=False, SECRET_KEY="test")
    with app.app_context():
        db.create_all()
        admin = User(username="admin_test", password=generate_password_hash("password"), role="admin", project="nasmedic", is_active_account=True)
        commercial = User(username="commercial_test", password=generate_password_hash("password"), role="commercial", project="nasmedic", is_active_account=True)
        db.session.add_all([admin, commercial])
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, username):
    return client.post("/login", data={"username": username, "password": "password"}, follow_redirects=False)


def test_admin_dashboard_requires_admin(client):
    login(client, "commercial_test")
    response = client.get("/admin_dashboard")
    assert response.status_code in (302, 403)


def test_commercial_dashboard_is_accessible_to_commercial(client):
    login(client, "commercial_test")
    response = client.get("/dashboard")
    assert response.status_code == 200


def test_admin_dashboard_is_accessible_to_admin(client):
    login(client, "admin_test")
    response = client.get("/admin_dashboard")
    assert response.status_code == 200


def test_unknown_url_returns_404(client):
    response = client.get("/route-that-does-not-exist")
    assert response.status_code == 404
