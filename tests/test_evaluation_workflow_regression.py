import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Evaluation, User


@pytest.fixture()
def evaluation_client():
    app = create_app(TestingConfig)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY="evaluation-test")
    with app.app_context():
        db.create_all()
        admin = User(
            username="evaluation_admin",
            password=generate_password_hash("admin-password"),
            role="admin",
            project="nasmedic",
            is_active_account=True,
        )
        commercial = User(
            username="evaluation_commercial",
            password=generate_password_hash("commercial-password"),
            role="commercial",
            project="nasmedic",
            zone="DAKAR",
            is_active_account=True,
        )
        db.session.add_all([admin, commercial])
        db.session.commit()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def login(client, username="evaluation_admin", password="admin-password"):
    response = client.post("/login", data={"username": username, "password": password})
    assert response.status_code == 302


def test_admin_can_save_evaluation_and_score_is_classified(evaluation_client):
    login(evaluation_client)

    response = evaluation_client.post(
        "/admin/evaluations/2/2026/10",
        data={
            "score_ca": "20",
            "score_gamme_asthe": "2",
            "score_gamme_myocalm": "2",
            "score_gamme_bumbum": "1",
            "score_gamme_flatupklexin": "2",
            "score_gamme_somniplex": "1",
            "score_gamme_ostheophytum": "1",
            "score_gamme_specialkid": "1",
            "score_reporting": "10",
            "score_plan_visite": "10",
            "score_argumentaire": "10",
            "score_prescriptions": "10",
            "score_organisation": "5",
            "score_ponctualite": "10",
            "score_consignes": "10",
            "score_esprit_equipe": "5",
            "points_forts": "Bonne couverture terrain",
            "axes_amelioration": "Renforcer le suivi",
            "objectifs_quantitatifs": "Atteindre les objectifs mensuels",
            "objectifs_qualitatifs": "Améliorer la qualité des visites",
            "submit": "Enregistrer l'évaluation",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "enregistrée".encode() in response.data
    with evaluation_client.application.app_context():
        evaluation = Evaluation.query.filter_by(
            commercial_id=2, year=2026, month=10
        ).one()
        assert evaluation.tenant_id == 116
        assert evaluation.total_score == pytest.approx(100)
        assert evaluation.niveau == "Excellent"
        assert evaluation.points_forts == "Bonne couverture terrain"


def test_classement_displays_saved_evaluation_and_classification(evaluation_client):
    login(evaluation_client)
    with evaluation_client.application.app_context():
        db.session.add(
            Evaluation(
                commercial_id=2,
                evaluator_id=1,
                year=2026,
                month=10,
                score_ca=20,
                score_gamme_asthe=2,
                score_gamme_myocalm=2,
                score_gamme_bumbum=1,
                score_gamme_flatupklexin=2,
                score_gamme_somniplex=1,
                score_gamme_ostheophytum=1,
                score_gamme_specialkid=1,
                score_reporting=10,
                score_plan_visite=10,
                score_argumentaire=10,
                score_prescriptions=10,
                score_organisation=5,
                score_ponctualite=10,
                score_consignes=10,
                score_esprit_equipe=5,
            )
        )
        db.session.commit()

    response = evaluation_client.get("/admin/classement?year=2026&month=10")
    assert response.status_code == 200
    assert b"evaluation_commercial" in response.data
    assert b"Excellent" in response.data


def test_commercial_cannot_access_admin_evaluation_pages(evaluation_client):
    login(evaluation_client, "evaluation_commercial", "commercial-password")
    response = evaluation_client.get("/admin/classement?year=2026&month=10")
    assert response.status_code in (403, 302)
