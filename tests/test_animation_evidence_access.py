"""Integration tests for animation evidence authorization by role and division."""

from datetime import date

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import AnimationEvidence, User


PASSWORD = "password"


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY="test")
    with app.app_context():
        db.create_all()
        users = [
            User(username="evidence_admin", password=generate_password_hash(PASSWORD), role="admin", project="nasmedic", is_active_account=True),
            User(username="evidence_vm_med", password=generate_password_hash(PASSWORD), role="commercial", project="nasmedic", is_active_account=True),
            User(username="evidence_vm_derm", password=generate_password_hash(PASSWORD), role="commercial", project="nasderm", is_active_account=True),
            User(username="evidence_animator_one", password=generate_password_hash(PASSWORD), role="animateur", project="nasmedic", is_active_account=True),
            User(username="evidence_animator_two", password=generate_password_hash(PASSWORD), role="animateur", project="nasmedic", is_active_account=True),
        ]
        db.session.add_all(users)
        db.session.flush()
        db.session.add_all([
            AnimationEvidence(
                animateur_id=users[3].id,
                pharmacy_name="Pharmacie Test Médic",
                animation_date=date(2026, 10, 30),
                project="nasmedic",
                filename="preuve.jpg",
                mime_type="image/jpeg",
                file_data=b"\\xff\\xd8\\xffpreuve",
                file_size=9,
            ),
            AnimationEvidence(
                animateur_id=users[3].id,
                pharmacy_name="Pharmacie Test Derm",
                animation_date=date(2026, 10, 30),
                project="nasderm",
                filename="preuve-derm.jpg",
                mime_type="image/jpeg",
                file_data=b"\\xff\\xd8\\xffpreuve",
                file_size=9,
            ),
            AnimationEvidence(
                animateur_id=users[4].id,
                pharmacy_name="Pharmacie Animateur Deux",
                animation_date=date(2026, 10, 30),
                project="nasmedic",
                filename="preuve-animateur-deux.jpg",
                mime_type="image/jpeg",
                file_data=b"\\xff\\xd8\\xffpreuve",
                file_size=9,
            ),
        ])
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, username):
    response = client.post(
        "/login",
        data={"username": username, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code in (200, 302)


def test_medical_visitor_can_view_evidence_in_own_division_only(client):
    login(client, "evidence_vm_med")
    assert client.get("/animations/ventes/justificatif/1").status_code == 200
    assert client.get("/animations/ventes/justificatif/2").status_code == 403


def test_animateur_can_view_only_own_evidence(client):
    login(client, "evidence_animator_two")
    assert client.get("/animations/ventes/justificatif/1").status_code == 403
    assert client.get("/animations/ventes/justificatif/3").status_code == 200


def test_admin_can_view_evidence_across_divisions(client):
    login(client, "evidence_admin")
    assert client.get("/animations/ventes/justificatif/2").status_code == 200
