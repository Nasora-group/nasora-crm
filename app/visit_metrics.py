"""KPI métier des visites terrain.

Une visite comptabilisée = un triplet unique (commercial, professionnel, date).
Les doublons historiques marqués is_duplicate=True sont exclus des KPI mais
restent conservés en base pour l'audit et l'historique.
"""

from datetime import timedelta

from sqlalchemy import func

from app.extensions import db
from app.models_clients import ClientVisit


def unique_visit_subquery(start_date=None, end_date=None, commercial_id=None):
    """Retourne les visites métier uniques, avec filtres optionnels."""
    query = db.session.query(
        ClientVisit.commercial_id.label("commercial_id"),
        ClientVisit.client_id.label("client_id"),
        ClientVisit.date.label("date"),
    ).filter(ClientVisit.is_duplicate.is_(False))

    if start_date is not None:
        query = query.filter(ClientVisit.date >= start_date)

    if end_date is not None:
        # Borne supérieure exclusive pour inclure toute la journée de fin,
        # y compris si ClientVisit.date est un DateTime avec une heure.
        query = query.filter(ClientVisit.date < end_date + timedelta(days=1))

    if commercial_id is not None:
        query = query.filter(ClientVisit.commercial_id == commercial_id)

    return query.distinct().subquery()


def unique_visit_count(start_date=None, end_date=None, commercial_id=None):
    """Nombre de visites métier uniques pour une période/commercial optionnels."""
    visits = unique_visit_subquery(start_date, end_date, commercial_id)
    return db.session.query(func.count()).select_from(visits).scalar() or 0


def unique_visits_by_commercial(start_date=None, end_date=None, commercial_id=None):
    """Retourne {commercial_id: nombre_de_visites_uniques} pour la période demandée."""
    visits = unique_visit_subquery(start_date, end_date, commercial_id)
    rows = (
        db.session.query(
            visits.c.commercial_id,
            func.count().label("nombre_visites"),
        )
        .group_by(visits.c.commercial_id)
        .all()
    )
    return {row.commercial_id: row.nombre_visites for row in rows}


def unique_visit_count_for_commercial(commercial_id, start_date=None, end_date=None):
    """Nombre de visites métier uniques pour un commercial et une période optionnelle."""
    return unique_visit_count(start_date, end_date, commercial_id)
