import pytest
from datetime import date
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import User, Prospection


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY="test")
    with app.app_context():
        db.create_all()
        admin = User(username="admin_revenue_test", password=generate_password_hash("password"), role="admin", project="nasmedic", is_active_account=True)
        nasmedic = User(username="commercial_nasmedic_test", password=generate_password_hash("password"), role="commercial", project="nasmedic", is_active_account=True)
        other_nasmedic = User(username="other_nasmedic_test", password=generate_password_hash("password"), role="commercial", project="nasmedic", is_active_account=True)
        nasderm = User(username="commercial_nasderm_test", password=generate_password_hash("password"), role="commercial", project="nasderm", is_active_account=True)
        db.session.add_all([admin, nasmedic, other_nasmedic, nasderm])
        db.session.flush()
        db.session.add(Prospection(commercial_id=other_nasmedic.id, date=date(2026, 8, 15), nom_client="Prospect autre commercial", specialite="PHARMACIEN", structure="PHARMACIES", telephone="770000000"))
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, username):
    return client.post("/login", data={"username": username, "password": "password"}, follow_redirects=False)


def test_commercial_cannot_open_other_division_revenue_dashboard(client):
    login(client, "commercial_nasmedic_test")
    response = client.get("/nasderm_dashboard")
    assert response.status_code in (302, 403)


def test_commercial_cannot_open_other_division_monthly_revenue(client):
    login(client, "commercial_nasmedic_test")
    response = client.get("/monthly_revenue_nasderm")
    assert response.status_code in (302, 403)


def test_commercial_cannot_open_other_division_revenue_detail(client):
    login(client, "commercial_nasmedic_test")
    response = client.get("/monthly_revenue_detail_nasderm/2026-08")
    assert response.status_code in (302, 403)


def test_commercial_revenue_dashboard_does_not_expose_same_division_colleague(client):
    login(client, "commercial_nasmedic_test")
    response = client.get("/nasmedic_dashboard")
    assert response.status_code == 200
    assert b"other_nasmedic_test" not in response.data
    assert "Prospect autre commercial".encode() not in response.data


def test_admin_can_open_both_division_revenue_dashboards(client):
    login(client, "admin_revenue_test")
    assert client.get("/nasmedic_dashboard").status_code == 200
    assert client.get("/nasderm_dashboard").status_code == 200
