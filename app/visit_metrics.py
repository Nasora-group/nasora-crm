"""KPI métier des visites terrain.

Une visite comptabilisée = un triplet unique (commercial, professionnel, date).
Les doublons historiques marqués is_duplicate=True sont exclus des KPI mais
restent conservés en base pour l'audit et l'historique.
"""

from sqlalchemy import func

from app.extensions import db
from app.models_clients import ClientVisit


def unique_visit_subquery():
    """Retourne les visites métier uniques sous forme de sous-requête SQL."""
    return (
        db.session.query(
            ClientVisit.commercial_id.label("commercial_id"),
            ClientVisit.client_id.label("client_id"),
            ClientVisit.date.label("date"),
        )
        .filter(ClientVisit.is_duplicate.is_(False))
        .distinct()
        .subquery()
    )


def unique_visit_count():
    """Nombre global de visites métier uniques."""
    visits = unique_visit_subquery()
    return db.session.query(func.count()).select_from(visits).scalar() or 0


def unique_visits_by_commercial():
    """Retourne {commercial_id: nombre_de_visites_uniques}."""
    visits = unique_visit_subquery()
    rows = (
        db.session.query(
            visits.c.commercial_id,
            func.count().label("nombre_visites"),
        )
        .group_by(visits.c.commercial_id)
        .all()
    )
    return {row.commercial_id: row.nombre_visites for row in rows}


def unique_visit_count_for_commercial(commercial_id):
    """Nombre de visites métier uniques pour un commercial."""
    visits = unique_visit_subquery()
    return (
        db.session.query(func.count())
        .select_from(visits)
        .filter(visits.c.commercial_id == commercial_id)
        .scalar()
        or 0
    )
