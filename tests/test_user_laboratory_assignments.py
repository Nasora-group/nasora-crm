import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Laboratory, User


@pytest.fixture()
def user_assignment_client():
    app = create_app(TestingConfig)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY="user-assignment-test")
    with app.app_context():
        db.create_all()
        admin = User(username="admin_assign", password=generate_password_hash("secret"), role="admin", project="nasmedic", is_active_account=True)
        db.session.add(admin)
        db.session.flush()
        lab_a = Laboratory(name="Lab Medic", slug="lab-medic", section="nasmedic", currency="XOF", is_active=True)
        lab_b = Laboratory(name="Lab Derm", slug="lab-derm", section="nasderm", currency="XOF", is_active=True)
        db.session.add_all([lab_a, lab_b])
        db.session.commit()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def _login(client):
    response = client.post("/login", data={"username": "admin_assign", "password": "secret"})
    assert response.status_code == 302


def test_admin_can_assign_user_to_selected_laboratory(user_assignment_client):
    _login(user_assignment_client)
    response = user_assignment_client.post(
        "/admin/utilisateurs/nouveau",
        data={
            "username": "vm_medic",
            "password": "password123",
            "role": "commercial",
            "project": "nasmedic",
            "zone": "CENTRE VILLE",
            "is_active_account": "y",
            "laboratory_ids": ["1"],
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with user_assignment_client.application.app_context():
        user = User.query.filter_by(username="vm_medic").one()
        assert user.project == "nasmedic"
        assert [lab.slug for lab in user.laboratories] == ["lab-medic"]


def test_user_cannot_be_assigned_to_laboratory_from_another_section(user_assignment_client):
    _login(user_assignment_client)
    response = user_assignment_client.post(
        "/admin/utilisateurs/nouveau",
        data={
            "username": "vm_wrong_section",
            "password": "password123",
            "role": "commercial",
            "project": "nasmedic",
            "is_active_account": "y",
            "laboratory_ids": ["2"],
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "ne correspondent pas à la section".encode() in response.data
    with user_assignment_client.application.app_context():
        assert User.query.filter_by(username="vm_wrong_section").first() is None


def test_dynamic_laboratory_sales_require_explicit_assignment(user_assignment_client):
    _login(user_assignment_client)
    user_assignment_client.post(
        "/admin/utilisateurs/nouveau",
        data={
            "username": "vm_no_lab",
            "password": "password123",
            "role": "commercial",
            "project": "nasmedic",
            "is_active_account": "y",
        },
        follow_redirects=True,
    )
    user_assignment_client.post("/logout", follow_redirects=True)
    response = user_assignment_client.post("/login", data={"username": "vm_no_lab", "password": "password123"})
    assert response.status_code == 302
    assert user_assignment_client.get("/admin/laboratoires/1/ventes").status_code == 403
