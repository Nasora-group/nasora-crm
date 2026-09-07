"""Synchronisation des deux représentations d'une visite réelle.

Règle métier NASORA : 1 visite réelle = 1 Prospection = 1 ClientVisit.
La synchronisation est centralisée ici pour éviter que les routes créent des
lignes miroir en double.
"""

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import Prospection
from app.models_clients import Client, ClientVisit


def _norm(value):
    return " ".join((value or "").strip().lower().split())


def _phone(value):
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _same_visit_payload(visit, prospect, client=None):
    if visit.commercial_id != prospect.commercial_id or visit.date != prospect.date:
        return False
    if (visit.products_presented or "") != (prospect.produits_presentes or ""):
        return False
    if (visit.products_prescribed or "") != (prospect.produits_prescrits or ""):
        return False
    if (visit.report or "") != (prospect.profils_prospect or ""):
        return False
    if client is not None:
        phone_match = bool(_phone(client.phone) and _phone(prospect.telephone) and _phone(client.phone) == _phone(prospect.telephone))
        name_match = bool(_norm(client.name) and _norm(client.name) == _norm(prospect.nom_client))
        if not (phone_match or name_match):
            return False
    return True


def _find_client_for_visit(visit):
    if visit.client is not None:
        return visit.client
    if visit.client_id is None:
        return None
    return db.session.get(Client, visit.client_id)


def _find_prospection_for_visit(visit):
    # Prefer an explicit link whenever present.
    if visit.prospection_id is not None:
        return db.session.get(Prospection, visit.prospection_id)
    client = _find_client_for_visit(visit)
    if client is None:
        return None
    candidates = Prospection.query.filter_by(commercial_id=visit.commercial_id, date=visit.date).order_by(Prospection.id.asc()).all()
    for prospect in candidates:
        if _same_visit_payload(visit, prospect, client):
            return prospect
    return None


def _find_client_for_prospection(prospection):
    prospect_phone = _phone(prospection.telephone)
    prospect_name = _norm(prospection.nom_client)
    candidates = Client.query.filter((Client.owner_id == prospection.commercial_id) | (Client.owner_id.is_(None))).all()
    for client in candidates:
        if prospect_phone and _phone(client.phone) and prospect_phone == _phone(client.phone):
            return client
        if prospect_name and prospect_name == _norm(client.name):
            return client
    return None


def _sync_client_fields(prospection, client):
    if client is None:
        client = Client(
            name=(prospection.nom_client or "").strip(),
            specialty=(prospection.specialite or "").strip() or None,
            structure=(prospection.structure or "").strip() or "Non renseignée",
            establishment=(prospection.establishment or "").strip() or None,
            phone=(prospection.telephone or "").strip() or None,
            potential=3,
            owner_id=prospection.commercial_id,
            last_visit=prospection.date,
        )
        db.session.add(client)
    else:
        client.name = (prospection.nom_client or "").strip() or client.name
        client.specialty = (prospection.specialite or "").strip() or client.specialty
        client.structure = (prospection.structure or "").strip() or client.structure
        if (prospection.establishment or "").strip():
            client.establishment = prospection.establishment.strip()
        if (prospection.telephone or "").strip():
            client.phone = prospection.telephone.strip()
        if client.owner_id is None:
            client.owner_id = prospection.commercial_id
    return client


def _find_visit_for_prospection(prospection):
    if prospection.id is not None:
        explicit = ClientVisit.query.filter_by(prospection_id=prospection.id, is_duplicate=False).first()
        if explicit is not None:
            return explicit
    client = _find_client_for_prospection(prospection)
    if client is None:
        return None
    candidates = ClientVisit.query.filter_by(client_id=client.id, commercial_id=prospection.commercial_id, date=prospection.date, is_duplicate=False).order_by(ClientVisit.id.asc()).all()
    for visit in candidates:
        if _same_visit_payload(visit, prospection, client):
            return visit
    return None


@event.listens_for(Session, "before_flush")
def synchronize_visit_records(session, flush_context, instances):
    """Complète automatiquement le miroir manquant, sans nested flush."""
    if session.info.get("visit_sync_running"):
        return
    session.info["visit_sync_running"] = True
    try:
        new_objects = list(session.new)
        new_visits = [obj for obj in new_objects if isinstance(obj, ClientVisit) and not obj.is_duplicate]
        new_prospects = [obj for obj in new_objects if isinstance(obj, Prospection)]

        paired_visit_ids = set()
        paired_prospect_ids = set()
        for visit in new_visits:
            client = _find_client_for_visit(visit)
            for prospect in new_prospects:
                if _same_visit_payload(visit, prospect, client):
                    paired_visit_ids.add(id(visit))
                    paired_prospect_ids.add(id(prospect))
                    # If both objects are explicitly supplied, link them now.
                    visit.prospection = prospect
                    break

        for visit in new_visits:
            if id(visit) in paired_visit_ids:
                continue
            if _find_prospection_for_visit(visit) is not None:
                continue
            client = _find_client_for_visit(visit)
            if client is None:
                continue
            session.add(Prospection(
                commercial_id=visit.commercial_id,
                date=visit.date,
                nom_client=client.name,
                specialite=client.specialty or "Non renseignée",
                structure=client.structure or "Non renseignée",
                telephone=client.phone or "NC",
                profils_prospect=visit.report,
                produits_presentes=visit.products_presented,
                produits_prescrits=visit.products_prescribed,
                establishment=client.establishment,
            ))

        for prospect in new_prospects:
            if id(prospect) in paired_prospect_ids:
                continue
            if _find_visit_for_prospection(prospect) is not None:
                continue
            client = _find_client_for_prospection(prospect)
            client = _sync_client_fields(prospect, client)
            visit = ClientVisit(
                client=client,
                prospection=prospect,
                commercial_id=prospect.commercial_id,
                date=prospect.date,
                products_presented=prospect.produits_presentes,
                products_prescribed=prospect.produits_prescrits,
                report=prospect.profils_prospect,
            )
            session.add(visit)
    finally:
        session.info.pop("visit_sync_running", None)
