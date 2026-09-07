"""Synchronisation fiable entre Prospection et ClientVisit."""

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
    if visit.prospection is not None:
        return visit.prospection
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
        if not client.last_visit or prospection.date >= client.last_visit:
            client.last_visit = prospection.date
    return client


def _linked_visits(session, prospection):
    if prospection.id is None:
        return [obj for obj in session.new if isinstance(obj, ClientVisit) and not obj.is_duplicate and (obj.prospection is prospection or obj.prospection_id == prospection.id)]
    visits = ClientVisit.query.filter_by(prospection_id=prospection.id, is_duplicate=False).order_by(ClientVisit.id.asc()).all()
    visits.extend(obj for obj in session.new if isinstance(obj, ClientVisit) and not obj.is_duplicate and obj.prospection is prospection)
    return visits


def _prepare_prospection_mirror(session, prospection):
    linked = _linked_visits(session, prospection)
    if linked:
        return
    client = _sync_client_fields(prospection, _find_client_for_prospection(prospection))
    session.add(ClientVisit(
        client=client,
        prospection=prospection,
        commercial_id=prospection.commercial_id,
        date=prospection.date,
        products_presented=prospection.produits_presentes or None,
        products_prescribed=prospection.produits_prescrits or None,
        report=prospection.profils_prospect or None,
    ))


def _merge_new_linked_visit(session, visit):
    """Une visite explicitement liée ne doit jamais créer une seconde ligne."""
    prospect = visit.prospection or (db.session.get(Prospection, visit.prospection_id) if visit.prospection_id else None)
    if prospect is None:
        return False
    existing = ClientVisit.query.filter_by(prospection_id=prospect.id, is_duplicate=False).order_by(ClientVisit.id.asc()).first()
    if existing is None:
        for obj in session.new:
            if isinstance(obj, ClientVisit) and obj is not visit and not obj.is_duplicate and obj.prospection is prospect:
                existing = obj
                break
    if existing is None or existing is visit:
        return False
    existing.client_id = visit.client_id or existing.client_id
    existing.commercial_id = visit.commercial_id
    existing.date = visit.date
    existing.products_presented = visit.products_presented
    existing.products_prescribed = visit.products_prescribed
    existing.report = visit.report
    existing.next_visit = visit.next_visit
    session.expunge(visit)
    return True


@event.listens_for(Session, "before_flush")
def prepare_visit_synchronization(session, flush_context, instances):
    if session.info.get("visit_sync_running"):
        return
    new_objects = list(session.new)
    new_prospects = [obj for obj in new_objects if isinstance(obj, Prospection)]
    new_visits = [obj for obj in new_objects if isinstance(obj, ClientVisit) and not obj.is_duplicate]
    pending = session.info.setdefault("pending_prospection_sync", [])
    for prospect in new_prospects:
        if prospect not in pending:
            pending.append(prospect)
    for visit in new_visits:
        if visit.prospection is not None or visit.prospection_id is not None:
            if _merge_new_linked_visit(session, visit):
                continue
            continue
        matched = next((prospect for prospect in pending if _same_visit_payload(visit, prospect, _find_client_for_visit(visit))), None)
        if matched is None:
            matched = _find_prospection_for_visit(visit)
        if matched is not None:
            visit.prospection = matched
            continue
        client = _find_client_for_visit(visit)
        if client is None:
            continue
        prospect = Prospection(
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
        )
        session.add(prospect)
        pending.append(prospect)
        visit.prospection = prospect


@event.listens_for(Session, "after_flush_postexec")
def finalize_prospection_synchronization(session, flush_context):
    if session.info.get("visit_sync_running"):
        return
    pending = session.info.pop("pending_prospection_sync", [])
    if not pending:
        return
    session.info["visit_sync_running"] = True
    try:
        for prospect in pending:
            _prepare_prospection_mirror(session, prospect)
    finally:
        session.info.pop("visit_sync_running", None)
