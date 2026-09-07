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
    if normalized_phone and not _invalid_phone(phone):
        candidates = Client.query.filter(
            Client.phone.isnot(None),
            (Client.owner_id.is_(None) | (Client.owner_id == prospection.commercial_id)),
        ).all()
        for client in candidates:
            if _normalize_phone(client.phone) == normalized_phone:
                return client
    if not normalized_name:
        return None
    same_name = [c for c in Client.query.filter(Client.name.isnot(None)).all() if _normalize_text(c.name) == normalized_name]
    owned = [c for c in same_name if c.owner_id in (None, prospection.commercial_id)]
    if owned:
        return sorted(owned, key=lambda c: (c.owner_id is not None, c.id))[0]
    return None


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
    visit = ClientVisit.query.filter_by(prospection_id=prospection.id, is_duplicate=False).first()
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
    prospection.client_id = client.id
    client.last_visit = prospection.date


def _sync_professional_from_existing_prospection(prospection, establishment=None, existing_client=None, previous_payload=None):
    return _sync_professional_from_prospection(prospection, establishment=establishment, existing_client=existing_client, previous_payload=previous_payload)


def _delete_linked_records_for_prospection(prospection):
    visit = ClientVisit.query.filter_by(prospection_id=prospection.id, is_duplicate=False).first()
    if visit is not None:
        visit.prospection_id = None
        db.session.delete(visit)
        return
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


@dashboard_bp.route("/dashboard", methods=["GET", "POST"])
@login_required
@roles_required("commercial")
def index():
    form = ProspectionForm()
    _set_structure_choices(form)
    _set_product_choices(form, current_user.project)
    if form.is_submitted():
        _set_structure_choices(form)
        _set_product_choices(form, current_user.project)
        if not form.validate():
            flash("Veuillez corriger les champs indiqués.", "error")
            return _render_dashboard(form)
        try:
            prospection = Prospection(
                commercial_id=current_user.id,
                date=form.date.data,
                nom_client=form.nom_client.data.strip(),
                specialite=form.specialite.data.strip(),
                structure=form.structure.data.strip(),
                telephone=form.telephone.data.strip(),
                profils_prospect=(form.profils_prospect.data or "").strip(),
                produits_presentes=", ".join(form.produits_presentes.data or []),
                produits_prescrits=", ".join(form.produits_prescrits.data or []),
                establishment=form.nom_structure.data.strip(),
            )
            db.session.add(prospection)
            # La route reste responsable de la transaction complète:
            # Prospection -> Client -> ClientVisit.
            db.session.flush()
            _sync_professional_from_prospection(
                prospection,
                establishment=form.nom_structure.data,
            )
            db.session.flush()
            linked_visits = ClientVisit.query.filter_by(
                prospection_id=prospection.id,
                is_duplicate=False,
            ).order_by(ClientVisit.id.asc()).all()
            for duplicate_visit in linked_visits[1:]:
                duplicate_visit.prospection_id = None
                db.session.delete(duplicate_visit)
            db.session.commit()
            flash("Prospection enregistrée avec succès.", "success")
            return redirect(url_for("dashboard.index"))
        except Exception:
            db.session.rollback()
            logger.exception("Erreur lors de l'enregistrement d'une prospection")
            flash("Impossible d'enregistrer la prospection. Aucun changement n'a été appliqué.", "error")
            return _render_dashboard(form)
    return _render_dashboard(form)


@dashboard_bp.route("/dashboard/prospections", methods=["GET"])
@login_required
@roles_required("commercial")
def prospections():
    rows = Prospection.query.filter_by(commercial_id=current_user.id).order_by(Prospection.date.desc(), Prospection.id.desc()).all()
    establishments_by_prospection = {}
    for row in rows:
        client = _find_client_for_prospection(row)
        establishments_by_prospection[row.id] = ((row.establishment or "").strip() or (client.establishment if client and client.establishment else ""))
    return render_template("dashboard_prospections.html", prospections=rows, planning_statuses={}, establishments_by_prospection=establishments_by_prospection)


@dashboard_bp.route("/dashboard/prospection/<int:prospection_id>/modifier", methods=["GET", "POST"])
@login_required
@roles_required("commercial")
def edit_prospection(prospection_id):
    prospection = Prospection.query.get_or_404(prospection_id)
    if prospection.commercial_id != current_user.id:
        return render_template("403.html"), 403
    existing_presentes = _parse_products(prospection.produits_presentes)
    existing_prescrits = _parse_products(prospection.produits_prescrits)
    form = ProspectionForm(obj=prospection)
    _set_structure_choices(form)
    _set_product_choices(form, current_user.project, set(existing_presentes) | set(existing_prescrits))
    if not form.is_submitted():
        form.produits_presentes.data = existing_presentes
        form.produits_prescrits.data = existing_prescrits
        client = _find_client_for_prospection(prospection)
        form.nom_structure.data = (prospection.establishment or (client.establishment if client else "")) or ""
    if form.validate_on_submit():
        try:
            linked_visit = ClientVisit.query.filter_by(prospection_id=prospection.id, is_duplicate=False).first()
            previous_client = linked_visit.client if linked_visit is not None else _find_client_for_prospection(prospection)
            previous_payload = {"client_id": previous_client.id if previous_client else None, "date": prospection.date, "products_presented": prospection.produits_presentes or None, "products_prescribed": prospection.produits_prescrits or None, "report": prospection.profils_prospect or None}
            prospection.date = form.date.data
            prospection.nom_client = form.nom_client.data.strip()
            prospection.specialite = form.specialite.data.strip()
            prospection.structure = form.structure.data.strip()
            prospection.establishment = form.nom_structure.data.strip()
            prospection.telephone = form.telephone.data.strip()
            prospection.profils_prospect = (form.profils_prospect.data or "").strip()
            prospection.produits_presentes = ", ".join(form.produits_presentes.data or [])
            prospection.produits_prescrits = ", ".join(form.produits_prescrits.data or [])
            _sync_professional_from_existing_prospection(prospection, form.nom_structure.data, existing_client=previous_client, previous_payload=previous_payload)
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
        return redirect(url_for("dashboard.prospections"))
    if form.validate_on_submit():
        try:
            _delete_linked_records_for_prospection(prospection)
            db.session.delete(prospection)
            db.session.commit()
            flash("Prospection supprimée avec succès.", "success")
        except Exception:
            db.session.rollback()
            logger.exception("Erreur lors de la suppression de la prospection #%s", prospection_id)
            flash("Impossible de supprimer la prospection. Aucun changement n'a été appliqué.", "error")
    return redirect(url_for("dashboard.prospections"))


def _visit_targets_for_commercials(commercials):
    """Read per-commercial visit targets with a safe 100-visit fallback."""
    targets = {commercial.id: 100 for commercial in commercials}
    if not commercials:
        return targets
    try:
        statement = text("SELECT commercial_id, target FROM visit_objective WHERE commercial_id IN :ids").bindparams(bindparam("ids", expanding=True))
        rows = db.session.execute(statement, {"ids": [commercial.id for commercial in commercials]}).mappings().all()
        for row in rows:
            targets[int(row["commercial_id"])] = int(row["target"])
    except Exception:
        db.session.rollback()
        logger.warning("Impossible de lire les objectifs de visites; fallback à 100.", exc_info=True)
    return targets


@dashboard_bp.route("/admin/dashboard-direction", methods=["GET"])
@login_required
@roles_required("admin")
def direction():
    """Dashboard Direction : pilotage de l'activité terrain, sans CA ni ventes."""
    date_start_raw = (request.args.get("date_start") or "").strip()
    date_end_raw = (request.args.get("date_end") or "").strip()
    commercial_raw = (request.args.get("commercial_id") or "").strip()
    zone = (request.args.get("zone") or "").strip()
    specialite = (request.args.get("specialite") or "").strip()

    def parse_date(value):
        try:
            return date.fromisoformat(value) if value else None
        except ValueError:
            return None

    date_start = parse_date(date_start_raw)
    date_end = parse_date(date_end_raw)
    commercial_id = int(commercial_raw) if commercial_raw.isdigit() else None

    query = Prospection.query.join(User, Prospection.commercial_id == User.id).filter(User.role == "commercial")
    if date_start:
        query = query.filter(Prospection.date >= date_start)
    if date_end:
        query = query.filter(Prospection.date <= date_end)
    if commercial_id:
        query = query.filter(Prospection.commercial_id == commercial_id)
    if zone:
        query = query.filter(User.zone == zone)
    if specialite:
        query = query.filter(Prospection.specialite == specialite)

    rows = query.all()
    total_prospections = len(rows)
    professionals = {professional_key(r) for r in rows if professional_key(r)}
    structures = {(_normalize_text(r.establishment or r.nom_client), r.commercial_id) for r in rows if _normalize_text(r.establishment or r.nom_client)}
    specialites_counter = Counter((r.specialite or "Non renseignée").strip() or "Non renseignée" for r in rows)
    zones_counter = Counter(((r.establishment or "Non renseignée").strip() or "Non renseignée") for r in rows)
    commerciaux = User.query.filter_by(role="commercial", is_active_account=True).order_by(User.username.asc()).all()
    visit_targets = _visit_targets_for_commercials(commerciaux)
    commercial_counts = Counter(r.commercial_id for r in rows)
    commercial_rows = [{"commercial": c, "count": commercial_counts.get(c.id, 0), "target": visit_targets.get(c.id, 100)} for c in commerciaux]
    return render_template("dashboard_direction.html", rows=rows, total_prospections=total_prospections, professionals=len(professionals), structures=len(structures), specialites_counter=specialites_counter, zones_counter=zones_counter, commerciaux=commerciaux, commercial_rows=commercial_rows, filters={"date_start": date_start_raw, "date_end": date_end_raw, "commercial_id": commercial_raw, "zone": zone, "specialite": specialite})