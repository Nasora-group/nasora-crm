"""KPI métier des visites terrain.

Règle métier NASORA : une visite réelle = une Prospection = un ClientVisit.
Prospection est la source de vérité pour les KPI de visites ; ClientVisit est
le miroir CRM utilisé pour l'historique professionnel.
"""

import re
import unicodedata
from datetime import timedelta

from sqlalchemy import func

from app.extensions import db
from app.models import Prospection


def _normalize_text(value):
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower()).strip())


def _normalize_phone(value):
    return re.sub(r"\D", "", value or "")


def professional_key(prospection):
    """Clé stable pour compter les professionnels distincts."""
    raw_phone = (prospection.telephone or "").strip().lower()
    phone = _normalize_phone(raw_phone)
    invalid_phone = (
        not raw_phone
        or raw_phone in {"na", "n/a", "nc", "non renseigne", "non renseigné", "0"}
        or len(phone) < 6
        or len(set(phone)) == 1
    )
    if not invalid_phone:
        return f"phone:{phone}"
    name = _normalize_text(prospection.nom_client)
    return f"name:{name}" if name else None


def unique_visit_subquery(start_date=None, end_date=None, commercial_id=None):
    """Retourne les visites métier issues des prospections, avec filtres."""
    query = db.session.query(
        Prospection.commercial_id.label("commercial_id"),
        Prospection.id.label("prospection_id"),
        Prospection.date.label("date"),
    )

    if start_date is not None:
        query = query.filter(Prospection.date >= start_date)

    if end_date is not None:
        query = query.filter(Prospection.date < end_date + timedelta(days=1))

    if commercial_id is not None:
        query = query.filter(Prospection.commercial_id == commercial_id)

    return query.subquery()


def unique_visit_count(start_date=None, end_date=None, commercial_id=None):
    """Nombre de visites réelles = nombre de prospections."""
    visits = unique_visit_subquery(start_date, end_date, commercial_id)
    return db.session.query(func.count()).select_from(visits).scalar() or 0


def unique_visits_by_commercial(start_date=None, end_date=None, commercial_id=None):
    """{commercial_id: visites} basé sur Prospection, source de vérité."""
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
    """Nombre de visites réelles pour un commercial et une période."""
    return unique_visit_count(start_date, end_date, commercial_id)
