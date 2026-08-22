"""Synchronisation bidirectionnelle des visites métier.

Règle métier : une visite réelle correspond à une Prospection et à un ClientVisit.
Le module garde les deux tables synchronisées pour les créations effectuées depuis
n'importe quelle partie du CRM.
"""

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import Prospection
from app.models_clients import Client, ClientVisit


def _norm(value):
    return " ".join((value or "").strip().lower().split())


def _find_client_for_visit(visit):
    client = db.session.get(Client, visit.client_id)
    return client


def _find_prospection_for_visit(visit):
    client = _find_client_for_visit(visit)
    if client is None:
        return None

    query = Prospection.query.filter_by(
        commercial_id=visit.commercial_id,
        date=visit.date,
        produits_presentes=visit.products_presented,
        produits_prescrits=visit.products_prescribed,
        profils_prospect=visit.report,
    )

    candidates = query.order_by(Prospection.id.asc()).all()
    client_phone = "".join(ch for ch in (client.phone or "") if ch.isdigit())
    client_name = _norm(client.name)

    for prospect in candidates:
        prospect_phone = "".join(ch for ch in (prospect.telephone or "") if ch.isdigit())
        prospect_name = _norm(prospect.nom_client)
        if client_phone and prospect_phone and client_phone == prospect_phone:
            return prospect
        if client_name and prospect_name == client_name:
            return prospect

    return None


def _find_visit_for_prospection(prospection):
    client_phone = "".join(ch for ch in (prospection.telephone or "") if ch.isdigit())
    client_name = _norm(prospection.nom_client)

    clients = Client.query.filter_by(owner_id=prospection.commercial_id).all()
    clients += Client.query.filter(Client.owner_id.is_(None)).all()

    for client in clients:
        phone = "".join(ch for ch in (client.phone or "") if ch.isdigit())
        name = _norm(client.name)
        if client_phone and phone and client_phone == phone or client_name and name == client_name:
            visit = ClientVisit.query.filter_by(
                client_id=client.id,
                commercial_id=prospection.commercial_id,
                date=prospection.date,
                is_duplicate=False,
            ).order_by(ClientVisit.id.asc()).first()
            if visit is not None:
                return visit
    return None


def _create_client_for_prospection(prospection):
    client = Client(
        name=prospection.nom_client.strip(),
        specialty=(prospection.specialite or "").strip() or None,
        structure=(prospection.structure or "").strip(),
        phone=(prospection.telephone or "").strip() or None,
        potential=3,
        owner_id=prospection.commercial_id,
        last_visit=prospection.date,
    )
    db.session.add(client)
    db.session.flush()
    return client


@event.listens_for(Session, "after_flush")
def synchronize_visit_records(session, flush_context):
    """Garantit l'équivalence Prospection <-> ClientVisit sans boucle de création."""
    if session.info.get("visit_sync_running"):
        return

    session.info["visit_sync_running"] = True
    try:
        # Une ClientVisit créée ailleurs que par le formulaire de prospection
        # crée automatiquement sa fiche Prospection correspondante.
        for visit in list(session.new):
            if not isinstance(visit, ClientVisit) or visit.is_duplicate:
                continue
            prospect = _find_prospection_for_visit(visit)
            if prospect is not None:
                continue
            client = _find_client_for_visit(visit)
            if client is None:
                continue
            session.add(Prospection(
                commercial_id=visit.commercial_id,
                date=visit.date,
                nom_client=client.name,
                specialite=client.specialty or "Non renseignée",
                structure=client.structure,
                telephone=client.phone or "NC",
                profils_prospect=visit.report,
                produits_presentes=visit.products_presented,
                produits_prescrits=visit.products_prescribed,
            ))

        # Une Prospection créée par un autre flux crée automatiquement sa
        # ClientVisit correspondante si elle n'existe pas déjà.
        for prospect in list(session.new):
            if not isinstance(prospect, Prospection):
                continue
            if _find_visit_for_prospection(prospect) is not None:
                continue
            client = None
            phone = "".join(ch for ch in (prospect.telephone or "") if ch.isdigit())
            name = _norm(prospect.nom_client)
            for candidate in Client.query.filter_by(owner_id=prospect.commercial_id).all():
                candidate_phone = "".join(ch for ch in (candidate.phone or "") if ch.isdigit())
                if (phone and candidate_phone and phone == candidate_phone) or (name and _norm(candidate.name) == name):
                    client = candidate
                    break
            if client is None:
                client = _create_client_for_prospection(prospect)
            session.add(ClientVisit(
                client_id=client.id,
                commercial_id=prospect.commercial_id,
                date=prospect.date,
                products_presented=prospect.produits_presentes,
                products_prescribed=prospect.produits_prescrits,
                report=prospect.profils_prospect,
            ))
    finally:
        session.info.pop("visit_sync_running", None)
