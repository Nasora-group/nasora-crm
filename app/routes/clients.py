from datetime import date
import re
import unicodedata

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from app.extensions import db
from app.models_clients import Client, ClientVisit
from app.models import Prospection, User
from app.utils.auth import roles_required

clients_bp = Blueprint("clients", __name__)


def _normalize_text(value):
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", value)


def _normalize_phone(value):
    return re.sub(r"\D", "", value or "")


def _legacy_matches(client, prospection):
    client_phone = _normalize_phone(client.phone)
    prospection_phone = _normalize_phone(prospection.telephone)
    if client_phone and prospection_phone and len(client_phone) >= 6 and client_phone == prospection_phone:
        return True
    client_name = _normalize_text(client.name)
    prospection_name = _normalize_text(prospection.client)
    return bool(client_name and prospection_name and client_name == prospection_name)


def _legacy_history_for_client(client):
    query = Prospection.query
    if current_user.role == "commercial":
        query = query.filter(Prospection.commercial_id == current_user.id)
    rows = query.order_by(Prospection.date.desc(), Prospection.id.desc()).all()
    return [row for row in rows if _legacy_matches(client, row)]


def _commercial_client_query():
    query = Client.query
    if current_user.role != "commercial":
        return query

    # Un commercial ne doit voir que les fiches qui lui sont attribuées
    # ou qui ne sont pas encore attribuées.
    query = query.filter(or_(Client.owner_id.is_(None), Client.owner_id == current_user.id))
    prospections = Prospection.query.filter_by(commercial_id=current_user.id).all()
    if not prospections:
        return query.filter(db.text("1 = 0"))

    phones = {_normalize_phone(p.telephone) for p in prospections if _normalize_phone(p.telephone)}
    names = {_normalize_text(p.client) for p in prospections if _normalize_text(p.client)}
    if not phones and not names:
        return query.filter(db.text("1 = 0"))

    conditions = []
    if phones:
        for phone in phones:
            digits = phone
            conditions.append(func.replace(func.replace(func.replace(func.replace(Client.phone, " ", ""), ".", ""), "-", ""), "+", "") == digits)
    if names:
        for name in names:
            conditions.append(func.lower(Client.name) == name)
    return query.filter(or_(*conditions))


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
    return ClientVisit.query.filter_by(
        client_id=client_id,
        commercial_id=commercial_id,
        date=visit_date,
        products_presented=products_presented,
        products_prescribed=products_prescribed,
        report=report,
        is_duplicate=False,
    ).first() is not None


@clients_bp.route("/admin/clients")
@login_required
@roles_required("admin", "commercial")
def clients_list():
    query = _commercial_client_query()
    search = request.args.get("q", "").strip()
    structure = request.args.get("structure", "").strip()
    potential = request.args.get("potential", "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Client.name.ilike(like), Client.phone.ilike(like), Client.structure.ilike(like), Client.specialty.ilike(like)))
    if structure:
        query = query.filter(Client.structure == structure)
    if potential:
        query = query.filter(Client.potential == potential)
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Client.name.asc()).paginate(page=page, per_page=25, error_out=False)
    all_visible = query.all()
    structures = len({(c.structure or "").strip().lower() for c in all_visible if (c.structure or "").strip()})
    high_potential = sum(1 for c in all_visible if _normalize_text(c.potential) in {"eleve", "high", "fort"})
    return render_template("admin_clients.html", clients=pagination.items, pagination=pagination, total=len(all_visible), structures=structures, high_potential=high_potential, search=search, structure=structure, potential=potential)


@clients_bp.route("/admin/clients/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "commercial")
def new_client():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        structure = request.form.get("structure", "").strip()
        duplicate, reason = _find_duplicate_client(phone, name, structure)
        if duplicate:
            flash(f"Un professionnel existe déjà avec ce {reason}. La fiche existante a été conservée.", "warning")
            return redirect(url_for("clients.client_detail", client_id=duplicate.id))
        try:
            owner_id = current_user.id if current_user.role == "commercial" else request.form.get("owner_id", type=int)
            client = Client(name=name, specialty=request.form.get("specialty", "").strip() or None, structure=structure or None, establishment=request.form.get("establishment", "").strip() or None, phone=phone or None, email=request.form.get("email", "").strip() or None, zone=request.form.get("zone", "").strip() or None, address=request.form.get("address", "").strip() or None, potential=request.form.get("potential", "").strip() or None, notes=request.form.get("notes", "").strip() or None, owner_id=owner_id)
            db.session.add(client)
            db.session.commit()
            flash("Professionnel enregistré avec succès.", "success")
            return redirect(url_for("clients.client_detail", client_id=client.id))
        except Exception:
            db.session.rollback()
            flash("Impossible d'enregistrer le professionnel.", "error")
    commercials = User.query.filter_by(role="commercial", is_active=True).order_by(User.username.asc()).all() if current_user.role == "admin" else []
    return render_template("client_form.html", client=None, commercials=commercials)


@clients_bp.route("/admin/clients/<int:client_id>/modifier", methods=["GET", "POST"])
@login_required
@roles_required("admin", "commercial")
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)
    if not _commercial_can_access_client(client):
        return render_template("403.html"), 403
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        structure = request.form.get("structure", "").strip()
        duplicate, reason = _find_duplicate_client(phone, name, structure, exclude_id=client.id)
        if duplicate:
            flash(f"Modification bloquée : un professionnel existe déjà avec ce {reason}.", "warning")
            return redirect(url_for("clients.edit_client", client_id=client.id))
        try:
            client.name = name
            client.specialty = request.form.get("specialty", "").strip() or None
            client.structure = structure or None
            client.establishment = request.form.get("establishment", "").strip() or None
            client.phone = phone or None
            client.email = request.form.get("email", "").strip() or None
            client.zone = request.form.get("zone", "").strip() or None
            client.address = request.form.get("address", "").strip() or None
            client.potential = request.form.get("potential", "").strip() or None
            client.notes = request.form.get("notes", "").strip() or None
            if current_user.role == "admin":
                client.owner_id = request.form.get("owner_id", type=int)
            db.session.commit()
            flash("Fiche professionnelle mise à jour.", "success")
            return redirect(url_for("clients.client_detail", client_id=client.id))
        except Exception:
            db.session.rollback()
            flash("Impossible de modifier la fiche professionnelle.", "error")
    commercials = User.query.filter_by(role="commercial", is_active=True).order_by(User.username.asc()).all() if current_user.role == "admin" else []
    return render_template("client_form.html", client=client, commercials=commercials)


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

    # Une simple consultation de la fiche ne doit jamais écrire en base.
    # Les champs persistés restent alimentés lors de l'enregistrement d'une visite.
    display_last_visit = client.last_visit
    if legacy_history and (not display_last_visit or legacy_history[0].date > display_last_visit):
        display_last_visit = legacy_history[0].date

    display_next_visit = client.next_visit
    latest_crm_next = next((v.next_visit for v in visits if v.next_visit), None)
    if latest_crm_next and (not display_next_visit or latest_crm_next != display_next_visit):
        display_next_visit = latest_crm_next

    presented_count = sum(1 for v in visits if (v.products_presented or "").strip()) + sum(1 for v in legacy_history if (v.produits_presentes or "").strip())
    prescribed_count = sum(1 for v in visits if (v.products_prescribed or "").strip()) + sum(1 for v in legacy_history if (v.produits_prescrits or "").strip())
    return render_template("client_detail.html", client=client, history=legacy_history, visits=visits, presented_count=presented_count, prescribed_count=prescribed_count, display_last_visit=display_last_visit, display_next_visit=display_next_visit)


@clients_bp.route("/admin/clients/<int:client_id>/visits/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "commercial")
def new_visit(client_id):
    client = Client.query.get_or_404(client_id)
    if not _commercial_can_access_client(client):
        return render_template("403.html"), 403
    if request.method == "POST":
        try:
            visit_date = request.form.get("date") or date.today().isoformat()
            next_visit = request.form.get("next_visit") or None
            visit_date_obj = date.fromisoformat(visit_date)
            next_visit_obj = date.fromisoformat(next_visit) if next_visit else None
            if next_visit_obj and next_visit_obj < visit_date_obj:
                flash("La prochaine visite ne peut pas être antérieure à la date de la visite.", "warning")
                return render_template("client_visit_form.html", client=client, today=visit_date)

            products_presented = request.form.get("products_presented", "").strip() or None
            products_prescribed = request.form.get("products_prescribed", "").strip() or None
            report = request.form.get("report", "").strip() or None

            # Un administrateur peut saisir une visite depuis la fiche d'un commercial :
            # si la fiche est déjà attribuée, l'historique doit rester rattaché à ce commercial.
            attributed_commercial_id = client.owner_id or current_user.id

            if _exact_visit_exists(client.id, attributed_commercial_id, visit_date_obj, products_presented, products_prescribed, report):
                flash("Cette visite existe déjà pour ce professionnel à cette date. Aucune nouvelle ligne n'a été créée.", "warning")
                return redirect(url_for("clients.client_detail", client_id=client.id))

            v = ClientVisit(client_id=client.id, commercial_id=attributed_commercial_id, date=visit_date_obj, products_presented=products_presented, products_prescribed=products_prescribed, report=report, next_visit=next_visit_obj)
            db.session.add(v)

            # Une saisie historique ne doit jamais faire reculer le dernier passage.
            previous_last_visit = client.last_visit
            if previous_last_visit is None or v.date >= previous_last_visit:
                client.last_visit = v.date
                client.next_visit = v.next_visit

            db.session.commit()
            flash("Visite enregistrée avec succès.", "success")
            return redirect(url_for("clients.client_detail", client_id=client.id))
        except Exception:
            db.session.rollback()
            flash("Impossible d'enregistrer la visite. Vérifiez les dates.", "error")
    return render_template("client_visit_form.html", client=client, today=date.today().isoformat())
