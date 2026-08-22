import datetime as dt

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Prospection, User
from app.models_clients import Client, ClientVisit


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY="test")
    with app.app_context():
        db.create_all()
        user = User(username="vm_sync", password=generate_password_hash("password"), role="commercial", project="nasmedic", is_active_account=True)
        db.session.add(user)
        db.session.flush()
        client = Client(name="Docteur Test", specialty="Médecin", structure="CLINIQUE", phone="770000000", owner_id=user.id)
        db.session.add(client)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


def test_client_visit_creates_one_prospection(app):
    with app.app_context():
        user = User.query.filter_by(username="vm_sync").one()
        client = Client.query.filter_by(name="Docteur Test").one()
        visit = ClientVisit(client_id=client.id, commercial_id=user.id, date=dt.date(2026, 8, 22), products_presented="ASTHE 1000", report="Compte rendu")
        db.session.add(visit)
        db.session.commit()
        assert ClientVisit.query.filter_by(is_duplicate=False).count() == 1
        assert Prospection.query.count() == 1


def test_prospection_creates_one_client_visit(app):
    with app.app_context():
        user = User.query.filter_by(username="vm_sync").one()
        prospect = Prospection(
            commercial_id=user.id,
            date=dt.date(2026, 8, 22),
            nom_client="Nouveau Prospect",
            specialite="Médecin",
            structure="CLINIQUE",
            telephone="771111111",
            produits_presentes="MYOCALM",
            produits_prescrits="MYOCALM",
        )
        db.session.add(prospect)
        db.session.commit()
        assert Prospection.query.count() == 1
        assert ClientVisit.query.filter_by(is_duplicate=False).count() == 1


def test_creating_both_sides_does_not_double_count(app):
    with app.app_context():
        user = User.query.filter_by(username="vm_sync").one()
        client = Client.query.filter_by(name="Docteur Test").one()
        prospect = Prospection(
            commercial_id=user.id,
            date=dt.date(2026, 8, 22),
            nom_client=client.name,
            specialite=client.specialty,
            structure=client.structure,
            telephone=client.phone,
            produits_presentes="ASTHE 1000",
            produits_prescrits="",
            profils_prospect="Compte rendu",
        )
        visit = ClientVisit(
            client_id=client.id,
            commercial_id=user.id,
            date=dt.date(2026, 8, 22),
            products_presented="ASTHE 1000",
            products_prescribed=None,
            report="Compte rendu",
        )
        db.session.add_all([prospect, visit])
        db.session.commit()
        assert Prospection.query.count() == 1
        assert ClientVisit.query.filter_by(is_duplicate=False).count() == 1
