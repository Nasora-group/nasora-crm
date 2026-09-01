import datetime as dt

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import User, Prospection
from app.models_clients import Client, ClientVisit
from app.routes.dashboard import _find_client_for_prospection


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


def test_new_prospection_creates_one_client_and_one_visit(app):
    with app.app_context():
        user = User.query.filter_by(username="integrity_vm").one()
        prospect = Prospection(
            commercial_id=user.id,
            date=dt.date(2026, 8, 25),
            nom_client="Dr Synchronisation",
            specialite="PEDIATRE",
            structure="CLINIQUE",
            telephone="773333333",
            profils_prospect="Service pédiatrie",
            produits_presentes="Produit A",
            produits_prescrits="Produit A",
        )
        db.session.add(prospect)
        db.session.commit()

        client = Client.query.filter_by(name="Dr Synchronisation", owner_id=user.id).one()
        visit = ClientVisit.query.filter_by(
            client_id=client.id,
            commercial_id=user.id,
            date=dt.date(2026, 8, 25),
            is_duplicate=False,
        ).one()

        assert client.specialty == "PEDIATRE"
        assert client.structure == "CLINIQUE"
        assert client.phone == "773333333"
        assert visit.products_presented == "Produit A"
        assert visit.products_prescribed == "Produit A"
        assert visit.report == "Service pédiatrie"


def test_existing_client_is_reused_for_same_commercial(app):
    with app.app_context():
        user = User.query.filter_by(username="integrity_vm").one()
        client = Client(
            name="Dr Existant",
            specialty="MEDECIN GENERALISTE",
            structure="HOPITAL",
            phone="774444444",
            owner_id=user.id,
            potential=3,
        )
        db.session.add(client)
        db.session.commit()

        prospect = Prospection(
            commercial_id=user.id,
            date=dt.date(2026, 8, 25),
            nom_client="Dr Existant",
            specialite="MEDECIN GENERALISTE",
            structure="HOPITAL",
            telephone="774444444",
        )
        db.session.add(prospect)
        db.session.commit()

        assert Client.query.filter_by(owner_id=user.id, name="Dr Existant").count() == 1
        assert ClientVisit.query.filter_by(client_id=client.id, commercial_id=user.id).count() == 1


def test_prospection_cannot_attach_to_another_commercial_client(app):
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
        foreign_client = Client(
            name="Dr Proprietaire Second",
            structure="CLINIQUE",
            phone="775555555",
            owner_id=second.id,
            potential=3,
        )
        db.session.add(foreign_client)
        db.session.flush()
        prospect = Prospection(
            commercial_id=first.id,
            date=dt.date(2026, 8, 26),
            nom_client="Dr Nouveau",
            specialite="PEDIATRE",
            structure="CLINIQUE",
            telephone="775555555",
        )
        db.session.add(prospect)
        db.session.commit()

        client = _find_client_for_prospection(prospect)
        assert client is not None
        assert client.id != foreign_client.id
        assert client.owner_id == first.id
        assert Client.query.filter_by(id=foreign_client.id, owner_id=second.id).one().phone == "775555555"


def test_linked_visit_cannot_be_modified_or_deleted_directly(app):
    with app.app_context():
        user = User.query.filter_by(username="integrity_vm").one()
        prospect = Prospection(
            commercial_id=user.id,
            date=dt.date(2026, 8, 27),
            nom_client="Dr Visite Liee",
            specialite="PEDIATRE",
            structure="CLINIQUE",
            telephone="776666666",
        )
        client = Client(
            name="Dr Visite Liee",
            structure="CLINIQUE",
            phone="776666666",
            owner_id=user.id,
            potential=3,
        )
        db.session.add_all([prospect, client])
        db.session.flush()
        visit = ClientVisit(
            client_id=client.id,
            commercial_id=user.id,
            prospection_id=prospect.id,
            date=prospect.date,
            report="Initial",
        )
        db.session.add(visit)
        db.session.commit()

        visit.report = "Modification directe"
        with pytest.raises(ValueError, match="doit être gérée depuis la prospection"):
            db.session.commit()
        db.session.rollback()

        visit = ClientVisit.query.filter_by(prospection_id=prospect.id).one()
        db.session.delete(visit)
        with pytest.raises(ValueError, match="doit être gérée depuis la prospection"):
            db.session.commit()
        db.session.rollback()
        assert ClientVisit.query.filter_by(prospection_id=prospect.id).count() == 1
