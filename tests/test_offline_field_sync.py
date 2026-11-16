import uuid

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import AnimationSale, OfflineSyncReceipt, Prospection, User


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        db.session.add_all([
            User(username="sync_commercial", password=generate_password_hash("password"), role="commercial", project="nasmedic", is_active_account=True),
            User(username="sync_animator", password=generate_password_hash("password"), role="animateur", project="nasmedic", is_active_account=True),
        ])
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, username):
    response = client.post("/login", data={"username": username, "password": "password"})
    assert response.status_code == 302


def test_offline_prospection_sync_creates_linked_crm_records_once(client, monkeypatch):
    monkeypatch.setattr("app.routes.dashboard.get_active_products_for_division", lambda _division: ["Produit A"])
    login(client, "sync_commercial")
    submission = {
        "submission_id": str(uuid.uuid4()),
        "date": "2026-11-16",
        "nom_client": "Dr Offline",
        "specialite": "Pédiatre",
        "structure": "CLINIQUE",
        "establishment": "Clinique Offline",
        "telephone": "771234567",
        "zone": "CENTRE VILLE",
        "region": "DAKAR",
        "address": "Dakar",
        "profils_prospect": "Visite hors connexion",
        "produits_presentes": ["Produit A"],
        "produits_prescrits": ["Produit A"],
        "hors_planning": False,
    }

    first = client.post("/api/offline-sync/prospection", json=submission)
    retry = client.post("/api/offline-sync/prospection", json=submission)

    assert first.status_code == 201
    assert first.json["status"] == "synced"
    assert retry.status_code == 200
    assert retry.json["duplicate"] is True
    with client.application.app_context():
        assert Prospection.query.count() == 1
        assert OfflineSyncReceipt.query.filter_by(submission_id=submission["submission_id"]).count() == 1


def test_offline_prospection_rejects_product_outside_user_division(client, monkeypatch):
    monkeypatch.setattr("app.routes.dashboard.get_active_products_for_division", lambda _division: ["Produit NASMEDIC"])
    login(client, "sync_commercial")
    submission = {
        "submission_id": str(uuid.uuid4()),
        "date": "2026-11-16",
        "nom_client": "Dr Refus",
        "specialite": "Pédiatre",
        "structure": "CLINIQUE",
        "establishment": "Clinique Refus",
        "telephone": "771234567",
        "zone": "CENTRE VILLE",
        "region": "DAKAR",
        "address": "Dakar",
        "profils_prospect": "",
        "produits_presentes": ["Produit NASDERM"],
        "produits_prescrits": [],
        "hors_planning": False,
    }

    response = client.post("/api/offline-sync/prospection", json=submission)

    assert response.status_code == 400
    with client.application.app_context():
        assert Prospection.query.count() == 0


def test_offline_animation_sync_saves_all_lines_once(client, monkeypatch):
    monkeypatch.setattr("app.routes.animation_sales.get_active_products_for_division", lambda _division: ["Produit A", "Produit B"])
    login(client, "sync_animator")
    submission = {
        "submission_id": str(uuid.uuid4()),
        "pharmacy_name": "Pharmacie Offline",
        "animation_date": "2026-11-16",
        "items": [
            {"product_name": "Produit A", "quantity": 2, "unit_price": "1500"},
            {"product_name": "Produit B", "quantity": 1, "unit_price": "2500.00"},
        ],
    }

    first = client.post("/animations/ventes/api/offline-sync", json=submission)
    retry = client.post("/animations/ventes/api/offline-sync", json=submission)

    assert first.status_code == 201
    assert len(first.json["entity_ids"]) == 2
    assert retry.status_code == 200
    assert retry.json["duplicate"] is True
    with client.application.app_context():
        assert AnimationSale.query.count() == 2
        assert OfflineSyncReceipt.query.filter_by(submission_id=submission["submission_id"]).count() == 1


def test_offline_animation_rejects_products_outside_user_division(client, monkeypatch):
    monkeypatch.setattr("app.routes.animation_sales.get_active_products_for_division", lambda _division: ["Produit A"])
    login(client, "sync_animator")
    response = client.post("/animations/ventes/api/offline-sync", json={
        "submission_id": str(uuid.uuid4()),
        "pharmacy_name": "Pharmacie Offline",
        "animation_date": "2026-11-16",
        "items": [{"product_name": "Produit NASDERM", "quantity": 2, "unit_price": "1500"}],
    })
    assert response.status_code == 400
    with client.application.app_context():
        assert AnimationSale.query.count() == 0
