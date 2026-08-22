import datetime as dt

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import User
from app.models_clients import Client, ClientVisit
from app.visit_metrics import (
    unique_visit_count,
    unique_visit_count_for_commercial,
    unique_visits_by_commercial,
)


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY="test")
    with app.app_context():
        db.create_all()
        users = [
            User(
                username=f"vm_{i}",
                password=generate_password_hash("password"),
                role="commercial",
                project="nasmedic",
                is_active_account=True,
            )
            for i in (5, 7)
        ]
        db.session.add_all(users)
        db.session.flush()
        clients = [
            Client(name="Client A", structure="Cabinet", owner_id=users[0].id),
            Client(name="Client B", structure="Cabinet", owner_id=users[0].id),
        ]
        db.session.add_all(clients)
        db.session.flush()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def seed(app):
    with app.app_context():
        users = {u.username: u for u in User.query.all()}
        clients = {c.name: c for c in Client.query.all()}
        d1 = dt.date(2026, 8, 21)
        d2 = dt.date(2026, 8, 22)
        db.session.add_all(
            [
                # One real visit.
                ClientVisit(client_id=clients["Client A"].id, commercial_id=users["vm_5"].id, date=d1),
                # Same business key, but historical duplicate: must not count.
                ClientVisit(
                    client_id=clients["Client A"].id,
                    commercial_id=users["vm_5"].id,
                    date=d1,
                    is_duplicate=True,
                ),
                # Same client/commercial on another day: a distinct business visit.
                ClientVisit(client_id=clients["Client A"].id, commercial_id=users["vm_5"].id, date=d2),
                # Same date/client, different commercial: distinct business visit.
                ClientVisit(client_id=clients["Client A"].id, commercial_id=users["vm_7"].id, date=d1),
                # Another client for commercial 7.
                ClientVisit(client_id=clients["Client B"].id, commercial_id=users["vm_7"].id, date=d2),
            ]
        )
        db.session.commit()
        return {"vm5": users["vm_5"].id, "vm7": users["vm_7"].id}


def test_unique_visit_count_excludes_historical_duplicates(app, seed):
    with app.app_context():
        assert ClientVisit.query.count() == 5
        assert ClientVisit.query.filter_by(is_duplicate=True).count() == 1
        assert unique_visit_count() == 4


def test_unique_visits_by_commercial(app, seed):
    with app.app_context():
        assert unique_visits_by_commercial() == {seed["vm5"]: 2, seed["vm7"]: 2}


def test_unique_visit_count_for_commercial(app, seed):
    with app.app_context():
        assert unique_visit_count_for_commercial(seed["vm5"]) == 2
        assert unique_visit_count_for_commercial(seed["vm7"]) == 2
        assert unique_visit_count_for_commercial(999999) == 0
