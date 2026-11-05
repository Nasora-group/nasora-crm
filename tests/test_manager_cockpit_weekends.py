from datetime import date

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Planning, User
from app.routes.manager_cockpit import _planned_visit_days, _planning_realization_detail
from app.utils import encode_planning_slot


@pytest.fixture()
def planning_app():
    app = create_app(TestingConfig)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY="test")
    with app.app_context():
        db.create_all()
        commercial = User(
            username="weekend_metrics_vm",
            password=generate_password_hash("password"),
            role="commercial",
            project="nasmedic",
            is_active_account=True,
        )
        db.session.add(commercial)
        db.session.flush()
        plan = Planning(
            commercial_id=commercial.id,
            date=date(2026, 10, 26),
            samedi=encode_planning_slot([
                ("PHARMACIES", "Pharmacie samedi"),
            ]),
            dimanche=encode_planning_slot([
                ("PHARMACIES", "Pharmacie dimanche 1"),
                ("CLINIQUE", "Clinique dimanche 2"),
            ]),
        )
        db.session.add(plan)
        db.session.commit()
        yield app, commercial.id
        db.session.remove()
        db.drop_all()


def test_manager_cockpit_counts_saturday_and_sunday_slots(planning_app):
    app, commercial_id = planning_app
    with app.app_context():
        total = _planned_visit_days(
            commercial_id,
            date(2026, 10, 31),
            date(2026, 11, 2),
        )

        assert total == 3


def test_visitor_detail_includes_weekend_plan_from_previous_monday(planning_app):
    app, commercial_id = planning_app
    with app.app_context():
        detail = _planning_realization_detail(
            commercial_id,
            date(2026, 11, 1),
            date(2026, 11, 2),
        )

        assert detail["planned"] == 2
        assert [row["date"] for row in detail["days"]] == [date(2026, 11, 1)]
        assert detail["days"][0]["planned"] == 2
