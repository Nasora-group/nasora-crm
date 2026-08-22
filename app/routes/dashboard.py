import logging
import re
import unicodedata

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.forms import ProspectionForm, CSRFOnlyForm
from app.models import Prospection, get_active_products_for_division
from app.models_clients import Client, ClientVisit
from app.utils import roles_required
from app.routes.revenue import _monthly_revenue_for_division, _objectives_kpis

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__)


def _parse_products(raw):
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _set_product_choices(form, division, existing_values=None):
    active_products = get_active_products_for_division(division)
    choices = [(name, name) for name in active_products]
    if existing_values:
        active_set = set(active_products)
        for value in existing_values:
            if value and value not in active_set:
                choices.append((value, f"{value} (non disponible)"))
                active_set.add(value)
    form.produits_presentes.choices = choices
    form.produits_prescrits.choices = choices


def _normalize_text(value):
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", value)


def _normalize_phone(value):
    return re.sub(r"\D", "", value or "")


def _invalid_phone(value):
    raw = (value or "").strip().lower()
    digits = _normalize_phone(raw)
    return raw in {"", "na", "n/a", "nc", "non renseigne", "non renseigné", "0"} or len(digits) < 6


def _find_client_for_prospection(prospection):
    phone = (prospection.telephone or "").strip()
    name = (prospection.nom_client or "").strip()
    normalized_phone = _normalize_phone(phone)
    normalized_name = _normalize_text(name)

    if normalized_phone and not _invalid_phone(phone):
        for client in Client.query.filter(Client.phone.isnot(None)).all():
            if _normalize_phone(client.phone) == normalized_phone:
                return client

    if not normalized_name:
        return None

    candidates = Client.query.filter(Client.name.isnot(None)).all()
    same_name = [client for client in candidates if _normalize_text(client.name) == normalized_name]
    owned = [client for client in same_name if client.owner_id == current_user.id]
    if owned:
        return sorted(owned, key=lambda client: client.id)[0]
    if len(same_name) == 1:
        return same_name[0]
    visited = [client for client in same_name if ClientVisit.query.filter_by(client_id=client.id, commercial_id=current_user.id).first() is not None]
    if visited:
        return sorted(visited, key=lambda client: client.id)[0]
    return None


def _sync_professional_from_prospection(prospection):
    phone = (prospection.telephone or "").strip()
    name = (prospection.nom_client or "").strip()
    client = _find_client_for_prospection(prospection)
    valid_phone = not _invalid_phone(phone)
    if client is None:
        client = Client(name=name, specialty=(prospection.specialite or "").strip() or None, structure=(prospection.structure or "").strip(), phone=phone if valid_phone else None, potential=3, owner_id=current_user.id, last_visit=prospection.date)
        db.session.add(client)
        db.session.flush()
    else:
        client.specialty = (prospection.specialite or "").strip() or client.specialty
        client.structure = (prospection.structure or "").strip() or client.structure
        if valid_phone:
            client.phone = phone
        if client.owner_id is None:
            client.owner_id = current_user.id
        if not client.last_visit or prospection.date > client.last_visit:
            client.last_visit = prospection.date
    visit = ClientVisit(client_id=client.id, commercial_id=current_user.id, date=prospection.date, products_presented=prospection.produits_presentes or None, products_prescribed=prospection.produits_prescrits or None, report=prospection.profils_prospect or None)
    db.session.add(visit)
    db.session.flush()
    return client, visit


def _sync_professional_from_existing_prospection(prospection):
    client = _find_client_for_prospection(prospection)
    phone = (prospection.telephone or "").strip()
    valid_phone = not _invalid_phone(phone)
    if client is None:
        client = Client(name=(prospection.nom_client or "").strip(), specialty=(prospection.specialite or "").strip() or None, structure=(prospection.structure or "").strip(), phone=phone if valid_phone else None, potential=3, owner_id=prospection.commercial_id, last_visit=prospection.date)
        db.session.add(client)
        db.session.flush()
    else:
        if valid_phone:
            client.phone = phone
        if client.owner_id is None:
            client.owner_id = prospection.commercial_id
        if not client.last_visit or prospection.date > client.last_visit:
            client.last_visit = prospection.date
    existing_visit = ClientVisit.query.filter_by(client_id=client.id, commercial_id=prospection.commercial_id, date=prospection.date, products_presented=prospection.produits_presentes or None, products_prescribed=prospection.produits_prescrits or None, report=prospection.profils_prospect or None).first()
    if existing_visit is None:
        db.session.add(ClientVisit(client_id=client.id, commercial_id=prospection.commercial_id, date=prospection.date, products_presented=prospection.produits_presentes or None, products_prescribed=prospection.produits_prescrits or None, report=prospection.profils_prospect or None))


def _render_dashboard(form):
    labels, totals, _ = _monthly_revenue_for_division(current_user.project)
    sales_kpis = _objectives_kpis(current_user.project, labels, totals)
    return render_template("dashboard.html", form=form, sales_kpis=sales_kpis)


@dashboard_bp.route("/dashboard", methods=["GET", "POST"])
@login_required
@roles_required("commercial")
def index():
    form = ProspectionForm()
    _set_product_choices(form, current_user.project)
    if form.is_submitted():
        if not form.validate():
            logger.warning("Prospection refusée pour %s: %s", current_user.username, form.errors)
            flash("Veuillez corriger les champs indiqués.", "error")
            return _render_dashboard(form)
        try:
            prospection = Prospection(commercial_id=current_user.id, date=form.date.data, nom_client=form.nom_client.data.strip(), specialite=form.specialite.data.strip(), structure=form.structure.data.strip(), telephone=form.telephone.data.strip(), profils_prospect=(form.profils_prospect.data or "").strip(), produits_presentes=", ".join(form.produits_presentes.data or []), produits_prescrits=", ".join(form.produits_prescrits.data or []))
            db.session.add(prospection)
            db.session.flush()
            client, visit = _sync_professional_from_prospection(prospection)
            db.session.commit()
            logger.info("Prospection #%s synchronisée avec Client #%s / Visit #%s pour %s", prospection.id, client.id, visit.id, current_user.username)
            flash("Prospection enregistrée avec succès.", "success")
            return redirect(url_for("dashboard.index"))
        except Exception:
            db.session.rollback()
            logger.exception("Erreur lors de l'enregistrement/synchronisation d'une prospection pour %s", current_user.username)
            flash("Impossible d'enregistrer la prospection. Vérifiez les données et réessayez.", "error")
            return _render_dashboard(form)
    return _render_dashboard(form)


@dashboard_bp.route("/dashboard/prospections", methods=["GET"])
@login_required
@roles_required("commercial")
def prospections():
    # Liste simple volontairement sans pagination : évite toute dépendance à l'API
    # de pagination de Flask-SQLAlchemy et garantit un affichage fiable du commercial.
    prospections = (
        Prospection.query
        .filter_by(commercial_id=current_user.id)
        .order_by(Prospection.date.desc(), Prospection.id.desc())
        .all()
    )
    return render_template("dashboard_prospections.html", prospections=prospections)


@dashboard_bp.route("/dashboard/prospection/<int:prospection_id>/modifier", methods=["GET", "POST"])
@login_required
@roles_required("commercial")
def edit_prospection(prospection_id):
    prospection = Prospection.query.get_or_404(prospection_id)
    if prospection.commercial_id != current_user.id:
        flash("Accès non autorisé : cette prospection ne t'appartient pas.", "error")
        return render_template("403.html"), 403
    existing_presentes = _parse_products(prospection.produits_presentes)
    existing_prescrits = _parse_products(prospection.produits_prescrits)
    form = ProspectionForm(obj=prospection)
    _set_product_choices(form, current_user.project, existing_values=set(existing_presentes) | set(existing_prescrits))
    if not form.is_submitted():
        form.produits_presentes.data = existing_presentes
        form.produits_prescrits.data = existing_prescrits
    if form.validate_on_submit():
        try:
            prospection.date = form.date.data
            prospection.nom_client = form.nom_client.data.strip()
            prospection.specialite = form.specialite.data.strip()
            prospection.structure = form.structure.data.strip()
            prospection.telephone = form.telephone.data.strip()
            prospection.profils_prospect = (form.profils_prospect.data or "").strip()
            prospection.produits_presentes = ", ".join(form.produits_presentes.data or [])
            prospection.produits_prescrits = ", ".join(form.produits_prescrits.data or [])
            _sync_professional_from_existing_prospection(prospection)
            db.session.commit()
            flash("Prospection mise à jour avec succès.", "success")
            return redirect(url_for("dashboard.prospections"))
        except Exception:
            db.session.rollback()
            logger.exception("Erreur lors de la modification de la prospection #%s", prospection_id)
            flash("Erreur lors de la mise à jour.", "error")
    return render_template("edit_prospection.html", form=form, prospection=prospection)


@dashboard_bp.route("/dashboard/prospection/<int:prospection_id>/supprimer", methods=["POST"])
@login_required
@roles_required("commercial")
def delete_prospection(prospection_id):
    form = CSRFOnlyForm()
    prospection = Prospection.query.get_or_404(prospection_id)
    if prospection.commercial_id != current_user.id:
        flash("Accès non autorisé : cette prospection ne t'appartient pas.", "error")
        return redirect(url_for("dashboard.prospections"))
    if form.validate_on_submit():
        db.session.delete(prospection)
        db.session.commit()
        flash("Prospection supprimée.", "success")
    return redirect(url_for("dashboard.prospections"))
