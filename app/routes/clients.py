from datetime import date
import re
import unicodedata
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from app.extensions import db
from app.models import User, Prospection, STRUCTURES
from app.models_clients import Client, ClientVisit
from app.utils import roles_required


clients_bp = Blueprint("clients", __name__)


def _normalize_text(value):
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", value)


def _normalize_phone(value):
    return re.sub(r"\D", "", value or "")


def _legacy_matches(client, visit):
    client_phone = _normalize_phone(client.phone)
    visit_phone = _normalize_phone(visit.telephone)
    if client_phone and visit_phone and client_phone == visit_phone:
        return True
    client_name = _normalize_text(client.name)
    visit_name = _normalize_text(visit.nom_client)
    if not client_name or not visit_name:
        return False
    if client_name == visit_name or client_name in visit_name or visit_name in client_name:
        return True
    client_tokens = {token for token in client_name.split() if len(token) >= 4}
    visit_tokens = {token for token in visit_name.split() if len(token) >= 4}
    common = client_tokens & visit_tokens
    return len(common) >= 2 or any(len(token) >= 7 for token in common)


def _legacy_history_for_client(client):
    filters = []
    if client.phone:
        filters.append(Prospection.telephone == client.phone)
    if client.name:
        filters.append(Prospection.nom_client.ilike(f"%{client.name}%"))
        normalized_name = _normalize_text(client.name)
        for token in normalized_name.split():
            if len(token) >= 5:
                filters.append(Prospection.nom_client.ilike(f"%{token}%"))
    query = Prospection.query.filter(or_(*filters)) if filters else Prospection.query.filter(False)
    if current_user.role == "commercial":
        query = query.filter(Prospection.commercial_id == current_user.id)
    candidates = query.order_by(Prospection.date.desc()).all()
    return [visit for visit in candidates if _legacy_matches(client, visit)]


def _commercial_client_query():
    active_prospections = Prospection.query.filter_by(commercial_id=current_user.id).all()
    if not active_prospections:
        return Client.query.filter(False)
    clients = Client.query.filter(or_(Client.owner_id.is_(None), Client.owner_id == current_user.id)).all()
    active_ids = set()
    for prospect in active_prospections:
        prospect_phone = _normalize_phone(prospect.telephone)
        prospect_name = _normalize_text(prospect.nom_client)
        if prospect_phone and len(prospect_phone) >= 6:
            for client in clients:
                if _normalize_phone(client.phone) == prospect_phone:
                    active_ids.add(client.id)
        if prospect_name:
            for client in clients:
                if _normalize_text(client.name) == prospect_name:
                    active_ids.add(client.id)
    if not active_ids:
        return Client.query.filter(False)
    return Client.query.filter(Client.id.in_(active_ids))


def _commercial_can_access_client(client):
    if current_user.role != "commercial":
        return True
    return client.owner_id in (None, current_user.id)


def _find_duplicate_client(phone, name, structure, exclude_id=None):
    normalized_phone = _normalize_phone(phone)
    normalized_name = _normalize_text(name)
    normalized_structure = _normalize_text(structure)
    query = Client.query
    if exclude_id is not None:
        query = query.filter(Client.id != exclude_id)
    candidates = query.all()
    for client in candidates:
        client_phone = _normalize_phone(client.phone)
        if normalized_phone and len(normalized_phone) >= 6 and client_phone and client_phone == normalized_phone:
            return client, "téléphone"
        if normalized_name and normalized_structure:
            if _normalize_text(client.name) == normalized_name and _normalize_text(client.structure) == normalized_structure:
                return client, "nom + structure"
    return None, None


def _exact_visit_exists(client_id, commercial_id, visit_date, products_presented, products_prescribed, report):
    return ClientVisit.query.filter_by(client_id=client_id, commercial_id=commercial_id, date=visit_date, products_presented=products_presented, products_prescribed=products_prescribed, report=report, is_duplicate=False).first() is not None


# ...

@clients_bp.route("/admin/clients/<int:client_id>")
@login_required
@roles_required("admin", "commercial")
def client_detail(client_id):
    client = Client.query.get_or_404(client_id)
    if not _commercial_can_access_client(client):
        return render_template("403.html"), 403
    legacy_history = _legacy_history_for_client(client)
    visits = ClientVisit.query.filter_by(client_id=client.id)
    if current_user.role == "commercial":
        visits = visits.filter(ClientVisit.commercial_id == current_user.id)
    visits = visits.order_by(ClientVisit.date.desc()).all()

    display_last_visit = client.last_visit
    if legacy_history and (not display_last_visit or legacy_history[0].date > display_last_visit):
        display_last_visit = legacy_history[0].date

    display_next_visit = client.next_visit
    latest_crm_next = next((v.next_visit for v in visits if v.next_visit), None)
    if latest_crm_next and (not display_next_visit or latest_crm_next != display_next_visit):
        display_next_visit = latest_crm_next

    # Une prospection liée à une ClientVisit représente la même activité terrain.
    # Elle ne doit être ni comptée ni affichée une seconde fois dans l’historique legacy.
    linked_prospection_ids = {v.prospection_id for v in visits if v.prospection_id is not None}
    unlinked_legacy_history = [p for p in legacy_history if p.id not in linked_prospection_ids]
    presented_count = sum(1 for v in visits if (v.products_presented or "").strip()) + sum(1 for p in unlinked_legacy_history if (p.produits_presentes or "").strip())
    prescribed_count = sum(1 for v in visits if (v.products_prescribed or "").strip()) + sum(1 for p in unlinked_legacy_history if (p.produits_prescrits or "").strip())
    return render_template("client_detail.html", client=client, history=unlinked_legacy_history, visits=visits, presented_count=presented_count, prescribed_count=prescribed_count, display_last_visit=display_last_visit, display_next_visit=display_next_visit)
