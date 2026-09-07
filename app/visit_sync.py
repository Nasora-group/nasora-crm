"""Synchronisation robuste entre Prospection et ClientVisit.

Règle métier NASORA : une visite réelle est représentée par une Prospection
et, lorsque possible, par une ClientVisit liée. La création d'une prospection
est d'abord persistée afin de disposer de son identifiant; le miroir CRM est
ensuite ajouté dans un second flush contrôlé.
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
        phone_match = bool(
            _phone(client.phone)
            and _phone(prospect.telephone)
            and _phone(client.phone) == _phone(prospect.telephone)
        )
        name_match = bool(
            _norm(client.name) and _norm(client.name) == _norm(prospect.nom_client)
        )
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
    if visit.prospection_id is not None:
        return db.session.get(Prospection, visit.prospection_id)

    client = _find_client_for_visit(visit)
    if client is None:
        return None

    candidates = (
        Prospection.query
        .filter_by(commercial_id=visit.commercial_id, date=visit.date)
        .order_by(Prospection.id.asc())
        .all()
    )
    for prospect in candidates:
        if _same_visit_payload(visit, prospect, client):
            return prospect
    return None


def _find_client_for_prospection(prospection):
    prospect_phone = _phone(prospection.telephone)
    prospect_name = _norm(prospection.nom_client)

    candidates = (
        Client.query
        .filter(
            (Client.owner_id == prospection.commercial_id)
            | (Client.owner_id.is_(None))
        )
        .all()
    )
    for client in candidates:
        if (
            prospect_phone
            and _phone(client.phone)
            and prospect_phone == _phone(client.phone)
        ):
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


def _create_visit_mirror(session, prospection):
    """Crée le miroir CRM après que la prospection possède un ID."""
    if prospection.id is None:
        return

    existing = (
        ClientVisit.query
        .filter_by(prospection_id=prospection.id, is_duplicate=False)
        .first()
    )
    if existing is not None:
        return

    client = _find_client_for_prospection(prospection)
    client = _sync_client_fields(prospection, client)

    session.add(
        ClientVisit(
            client=client,
            prospection=prospection,
            commercial_id=prospection.commercial_id,
            date=prospection.date,
            products_presented=prospection.produits_presentes or None,
            products_prescribed=prospection.produits_prescrits or None,
            report=prospection.profils_prospect or None,
        )
    )


@event.listens_for(Session, "before_flush")
def synchronize_new_visit_records(session, flush_context, instances):
    """Synchronise uniquement les visites créées directement."""
    if session.info.get("visit_sync_running"):
        return

    new_objects = list(session.new)
    new_visits = [
        obj
        for obj in new_objects
        if isinstance(obj, ClientVisit) and not obj.is_duplicate
    ]
    new_prospects = [
        obj for obj in new_objects if isinstance(obj, Prospection)
    ]

    # La prospection sera traitée après son premier flush, quand son ID
    # existe réellement. On ne crée donc plus de Client/ClientVisit pendant
    # le flush initial de la prospection.
    if new_prospects:
        pending = session.info.setdefault("pending_prospection_sync", [])
        for prospect in new_prospects:
            if prospect not in pending:
                pending.append(prospect)

    for visit in new_visits:
        # Une visite déjà liée à une prospection ne doit jamais créer un miroir.
        if visit.prospection_id is not None or visit.prospection is not None:
            continue
        if _find_prospection_for_visit(visit) is not None:
            continue

        client = _find_client_for_visit(visit)
        if client is None:
            continue

        session.add(
            Prospection(
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
        )


@event.listens_for(Session, "after_flush_postexec")
def synchronize_pending_prospections(session, flush_context):
    """Ajoute les miroirs CRM après le flush qui attribue les IDs."""
    pending = session.info.pop("pending_prospection_sync", [])
    if not pending or session.info.get("visit_sync_after_flush"):
        return

    session.info["visit_sync_after_flush"] = True
    try:
        for prospect in pending:
            _create_visit_mirror(session, prospect)
    finally:
        session.info.pop("visit_sync_after_flush", None)
