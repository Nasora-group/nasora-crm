import datetime as dt
import uuid

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import OfflineSyncReceipt, Planning, User


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        users = [
            User(username="offline_vm_a", password=generate_password_hash("password"), role="commercial", project="nasmedic", is_active_account=True),
            User(username="offline_vm_b", password=generate_password_hash("password"), role="commercial", project="nasderm", is_active_account=True),
        ]
        db.session.add_all(users)
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


def payload(submission_id=None):
    return {
        "submission_id": submission_id or str(uuid.uuid4()),
        "date": "2026-11-16",
        "slots": {
            day: ([{"structure": "PHARMACIES", "name": "Pharmacie Test"}] if day == "lundi" else [])
            for day in ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
        },
    }


def test_offline_planning_sync_requires_authenticated_commercial(client):
    response = client.post("/api/offline-sync/planning", json=payload())
    assert response.status_code == 401


def test_offline_planning_sync_is_idempotent_for_same_user(client):
    login(client, "offline_vm_a")
    submission = payload()

    first = client.post("/api/offline-sync/planning", json=submission)
    retry = client.post("/api/offline-sync/planning", json=submission)

    assert first.status_code == 201
    assert first.json["status"] == "synced"
    assert first.json["duplicate"] is False
    assert retry.status_code == 200
    assert retry.json["duplicate"] is True

    with client.application.app_context():
        assert Planning.query.filter_by(date=dt.date(2026, 11, 16)).count() == 1
        assert OfflineSyncReceipt.query.filter_by(submission_id=submission["submission_id"]).count() == 1


def test_offline_sync_receipt_is_scoped_to_authenticated_user(client):
    submission = payload()
    login(client, "offline_vm_a")
    first = client.post("/api/offline-sync/planning", json=submission)
    assert first.status_code == 201

    client.post("/logout")
    login(client, "offline_vm_b")
    second = client.post("/api/offline-sync/planning", json=submission)

    assert second.status_code == 201
    assert second.json["duplicate"] is False
    with client.application.app_context():
        assert Planning.query.count() == 2
        assert OfflineSyncReceipt.query.filter_by(submission_id=submission["submission_id"]).count() == 2


@pytest.mark.parametrize("date_value", ["2026-11-17", "not-a-date"])
def test_offline_planning_sync_rejects_invalid_week_start(client, date_value):
    login(client, "offline_vm_a")
    submission = payload()
    submission["date"] = date_value

    response = client.post("/api/offline-sync/planning", json=submission)

    assert response.status_code == 400
    assert Planning.query.count() == 0


def test_offline_planning_sync_rejects_unknown_structure(client):
    login(client, "offline_vm_a")
    submission = payload()
    submission["slots"]["lundi"] = [{"structure": "AUTRE", "name": "Pharmacie Test"}]

    response = client.post("/api/offline-sync/planning", json=submission)

    assert response.status_code == 400
    with client.application.app_context():
        assert Planning.query.count() == 0
