import logging
import re
import unicodedata
from collections import Counter
from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import bindparam, func, text

from app.extensions import db
from app.forms import ProspectionForm, CSRFOnlyForm
from app.models import Prospection, User, get_active_products_for_division, STRUCTURES
from app.models_clients import Client, ClientVisit
from app.utils import roles_required
from app.routes.revenue import _monthly_revenue_for_division, _objectives_kpis
from app.visit_metrics import professional_key

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__)


def _parse_products(raw):
    return [p.strip() for p in (raw or "").split(",") if p.strip()]


def _set_product_choices(form, division, existing_values=None):
    active = get_active_products_for_division(division)
    choices = [(name, name) for name in active]
    for value in (existing_values or []):
        if value and value not in active:
            choices.append((value, f"{value} (non disponible)"))
    form.produits_presentes.choices = choices
    form.produits_prescrits.choices = choices


def _set_structure_choices(form):
    form.structure.choices = [(value, label) for value, label in STRUCTURES]


def _normalize_text(value):
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower()).strip())


def _normalize_phone(value):
    return re.sub(r"\D", "", value or "")


def _invalid_phone(value):
    raw = (value or "").strip().lower()
    return raw in {"", "na", "n/a", "nc", "non renseigne", "non renseigné", "0"} or len(_normalize_phone(raw)) < 6


def _find_client_for_prospection(prospection):
    phone = (prospection.telephone or "").strip()
    name = (prospection.nom_client or "").strip()
    normalized_phone = _normalize_phone(phone)
    normalized_name = _normalize_text(name)

    # A commercial must never attach a prospection to a client owned by
    # another commercial. Admins retain the global matching behavior.
    client_query = Client.query
    if current_user.role == "commercial":
        client_query = client_query.filter(
            (Client.owner_id.is_(None)) | (Client.owner_id == current_user.id)
        )

    if normalized_phone and not _invalid_phone(phone):
        for client in client_query.filter(Client.phone.isnot(None)).all():
            if _normalize_phone(client.phone) == normalized_phone:
                return client
    if not normalized_name:
        return None
    same_name = [c for c in client_query.filter(Client.name.isnot(None)).all() if _normalize_text(c.name) == normalized_name]
    owned = [c for c in same_name if c.owner_id == prospection.commercial_id]
    if owned:
        return sorted(owned, key=lambda c: c.id)[0]
    return same_name[0] if len(same_name) == 1 else None


def _sync_client_fields(prospection, client, establishment=None):
    phone = (prospection.telephone or "").strip()
    valid_phone = not _invalid_phone(phone)
    establishment = (establishment or "").strip() or None
    if client is None:
        client = Client(
            name=prospection.nom_client.strip(),
            specialty=prospection.specialite.strip() or None,
            structure=prospection.structure.strip(),
            establishment=establishment,
            phone=phone if valid_phone else None,
            potential=3,
            owner_id=prospection.commercial_id,
            last_visit=prospection.date,
        )
        db.session.add(client)
        db.session.flush()
    else:
        client.name = prospection.nom_client.strip() or client.name
        client.specialty = prospection.specialite.strip() or client.specialty
        client.structure = prospection.structure.strip() or client.structure
        if establishment:
            client.establishment = establishment
        if valid_phone:
            client.phone = phone
        if client.owner_id is None:
            client.owner_id = prospection.commercial_id
    return client


def _sync_professional_from_prospection(prospection, establishment=None, existing_client=None, previous_payload=None):
    client = existing_client or _find_client_for_prospection(prospection)
    client = _sync_client_fields(prospection, client, establishment=establishment)

    pp = prospection.produits_presentes or None
    pr = prospection.produits_prescrits or None
    report = prospection.profils_prospect or None

    visit = ClientVisit.query.filter_by(
        prospection_id=prospection.id,
        is_duplicate=False,
    ).first()

    # Legacy prospections created before the explicit link can be attached only
    # to an exact old visit. Never guess from date alone.
    if visit is None and previous_payload and previous_payload.get("client_id"):
        visit = ClientVisit.query.filter_by(
            client_id=previous_payload["client_id"],
            commercial_id=prospection.commercial_id,
            date=previous_payload["date"],
            products_presented=previous_payload["products_presented"],
            products_prescribed=previous_payload["products_prescribed"],
            report=previous_payload["report"],
            is_duplicate=False,
        ).first()
        if visit is not None and visit.prospection_id is None:
            visit.prospection_id = prospection.id

    if visit is None:
        visit = ClientVisit(
            client_id=client.id,
            commercial_id=prospection.commercial_id,
            prospection_id=prospection.id,
            date=prospection.date,
            products_presented=pp,
            products_prescribed=pr,
            report=report,
        )
        db.session.add(visit)
    else:
        visit.client_id = client.id
        visit.commercial_id = prospection.commercial_id
        visit.prospection_id = prospection.id
        visit.date = prospection.date
        visit.products_presented = pp
        visit.products_prescribed = pr
        visit.report = report

    # Recalcul uniquement à partir des visites de ce professionnel.
    latest_client_visit_date = db.session.query(func.max(ClientVisit.date)).filter(
        ClientVisit.client_id == client.id,
        ClientVisit.is_duplicate.is_(False),
    ).scalar()
    client.last_visit = latest_client_visit_date or prospection.date


def _sync_professional_from_existing_prospection(prospection, establishment=None, existing_client=None, previous_payload=None):
    return _sync_professional_from_prospection(
        prospection,
        establishment=establishment,
        existing_client=existing_client,
        previous_payload=previous_payload,
    )


def _delete_linked_records_for_prospection(prospection):
    # New records have an unambiguous link: delete only that exact visit.
    visit = ClientVisit.query.filter_by(
        prospection_id=prospection.id,
        is_duplicate=False,
    ).first()
    if visit is not None:
        db.session.delete(visit)
        return

    # For legacy rows without a link, delete only an exact payload match.
    client = _find_client_for_prospection(prospection)
    if client is None:
        return
    pp = prospection.produits_presentes or None
    pr = prospection.produits_prescrits or None
    report = prospection.profils_prospect or None
    visit = ClientVisit.query.filter_by(
        client_id=client.id,
        commercial_id=prospection.commercial_id,
        date=prospection.date,
        products_presented=pp,
        products_prescribed=pr,
        report=report,
        is_duplicate=False,
        prospection_id=None,
    ).first()
    if visit is not None:
        db.session.delete(visit)


def _render_dashboard(form):
    labels, totals, _ = _monthly_revenue_for_division(current_user.project)
    sales_kpis = _objectives_kpis(current_user.project, labels, totals)
    return render_template("dashboard.html", form=form, sales_kpis=sales_kpis)
