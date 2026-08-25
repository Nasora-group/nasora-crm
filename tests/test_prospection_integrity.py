import datetime as dt

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import User, Prospection


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        user = User(
            username="integrity_vm",
            password=generate_password_hash("password"),
            role="commercial",
            project="nasmedic",
            is_active_account=True,
        )
        db.session.add(user)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


def test_prospection_preserves_required_business_fields(app):
    with app.app_context():
        user = User.query.filter_by(username="integrity_vm").one()
        prospect = Prospection(
            commercial_id=user.id,
            date=dt.date(2026, 8, 25),
            nom_client="Dr Test",
            specialite="MEDECIN GENERALISTE",
            structure="CLINIQUE",
            telephone="770000000",
        )
        db.session.add(prospect)
        db.session.commit()

        saved = Prospection.query.one()
        assert saved.commercial_id == user.id
        assert saved.date == dt.date(2026, 8, 25)
        assert saved.nom_client == "Dr Test"
        assert saved.specialite == "MEDECIN GENERALISTE"
        assert saved.structure == "CLINIQUE"
        assert saved.telephone == "770000000"


def test_prospections_are_isolated_by_commercial(app):
    with app.app_context():
        first = User.query.filter_by(username="integrity_vm").one()
        second = User(
            username="integrity_vm_2",
            password=generate_password_hash("password"),
            role="commercial",
            project="nasmedic",
            is_active_account=True,
        )
        db.session.add(second)
        db.session.flush()
        db.session.add_all([
            Prospection(
                commercial_id=first.id,
                date=dt.date(2026, 8, 25),
                nom_client="Prospect A",
                specialite="PEDIATRE",
                structure="CLINIQUE",
                telephone="771111111",
            ),
            Prospection(
                commercial_id=second.id,
                date=dt.date(2026, 8, 25),
                nom_client="Prospect B",
                specialite="INFIRMIER",
                structure="CENTRE DE SANTE",
                telephone="772222222",
            ),
        ])
        db.session.commit()

        assert Prospection.query.filter_by(commercial_id=first.id).count() == 1
        assert Prospection.query.filter_by(commercial_id=second.id).count() == 1
