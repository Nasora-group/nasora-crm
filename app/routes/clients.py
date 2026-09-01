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


@clients_bp.route("/admin/clients")
@login_required
@roles_required("admin", "commercial")
def list_clients():
    q = (request.args.get("q") or "").strip()
    structure = (request.args.get("structure") or "").strip()
    potential = (request.args.get("potential") or "").strip()
    query = Client.query
    if current_user.role == "commercial":
        query = _commercial_client_query()
    if q:
        term = f"%{q}%"
        query = query.filter(or_(Client.name.ilike(term), Client.establishment.ilike(term), Client.phone.ilike(term), Client.zone.ilike(term)))
    if structure:
        query = query.filter(Client.structure == structure)
    if potential:
        query = query.filter(Client.potential == int(potential))
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Client.name.asc()).paginate(page=page, per_page=25, error_out=False)
    total = query.with_entities(func.count(func.distinct(Client.id))).scalar() or 0
    structures = query.with_entities(func.count(func.distinct(Client.structure))).scalar() or 0
    high_potential = query.filter(Client.potential >= 4).with_entities(func.count(func.distinct(Client.id))).scalar() or 0
    return render_template("admin_clients.html", clients=pagination.items, pagination=pagination, total=total, structures=structures, high_potential=high_potential, q=q, structure=structure, potential=potential, structure_choices=[s[0] for s in STRUCTURES])


@clients_bp.route("/admin/clients/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "commercial")
def new_client():
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            structure = request.form.get("structure", "").strip()
            if not name or not structure:
                flash("Le nom et la structure sont obligatoires.", "error")
                return render_template("client_form.html", client=None, structure_choices=[s[0] for s in STRUCTURES], commerciaux=User.query.filter_by(role="commercial", is_active_account=True).order_by(User.username).all())
            duplicate, match_type = _find_duplicate_client(request.form.get("phone", ""), name, structure)
            if duplicate:
                flash(f"Un professionnel existe déjà avec ce {match_type}. Consultez sa fiche avant d'en créer une nouvelle.", "warning")
                return redirect(url_for("clients.client_detail", client_id=duplicate.id))
            potential = max(1, min(5, int(request.form.get("potential", 3))))
            owner_id = current_user.id if current_user.role == "commercial" else (request.form.get("owner_id", type=int) or None)
            c = Client(name=name, specialty=request.form.get("specialty", "").strip() or None, structure=structure, establishment=request.form.get("establishment", "").strip() or None, phone=request.form.get("phone", "").strip() or None, email=request.form.get("email", "").strip() or None, zone=request.form.get("zone", "").strip() or None, address=request.form.get("address", "").strip() or None, potential=potential, notes=request.form.get("notes", "").strip() or None, owner_id=owner_id)
            db.session.add(c); db.session.commit(); flash("Professionnel ajouté à la base CRM.", "success"); return redirect(url_for("clients.client_detail", client_id=c.id))
        except Exception:
            db.session.rollback(); flash("Impossible d'enregistrer le professionnel.", "error")
    return render_template("client_form.html", client=None, structure_choices=[s[0] for s in STRUCTURES], commerciaux=User.query.filter_by(role="commercial", is_active_account=True).order_by(User.username).all())


@clients_bp.route("/admin/clients/<int:client_id>/modifier", methods=["GET", "POST"])
@login_required
@roles_required("admin", "commercial")
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)
    if not _commercial_can_access_client(client):
        return render_template("403.html"), 403
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            structure = request.form.get("structure", "").strip()
            if not name or not structure:
                flash("Le nom et la structure sont obligatoires.", "error")
                return render_template("client_form.html", client=client, structure_choices=[s[0] for s in STRUCTURES], commerciaux=[])
            duplicate, match_type = _find_duplicate_client(request.form.get("phone", ""), name, structure, exclude_id=client.id)
            if duplicate:
                flash(f"Modification bloquée : un autre professionnel existe déjà avec ce {match_type}.", "warning")
                return render_template("client_form.html", client=client, structure_choices=[s[0] for s in STRUCTURES], commerciaux=[])
            client.name = name
            client.specialty = request.form.get("specialty", "").strip() or None
            client.structure = structure
            client.establishment = request.form.get("establishment", "").strip() or None
            client.phone = request.form.get("phone", "").strip() or None
            client.email = request.form.get("email", "").strip() or None
            client.zone = request.form.get("zone", "").strip() or None
            client.address = request.form.get("address", "").strip() or None
            client.potential = max(1, min(5, int(request.form.get("potential", 3))))
            client.notes = request.form.get("notes", "").strip() or None
            db.session.commit()
            flash("Fiche professionnel mise à jour avec succès.", "success")
            return redirect(url_for("clients.client_detail", client_id=client.id))
        except Exception:
            db.session.rollback(); flash("Impossible de mettre à jour le professionnel.", "error")
    return render_template("client_form.html", client=client, structure_choices=[s[0] for s in STRUCTURES], commerciaux=[])


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
            attributed_commercial_id = client.owner_id or current_user.id
            if _exact_visit_exists(client.id, attributed_commercial_id, visit_date_obj, products_presented, products_prescribed, report):
                flash("Cette visite existe déjà pour ce professionnel à cette date. Aucune nouvelle ligne n'a été créée.", "warning")
                return redirect(url_for("clients.client_detail", client_id=client.id))
            v = ClientVisit(client_id=client.id, commercial_id=attributed_commercial_id, date=visit_date_obj, products_presented=products_presented, products_prescribed=products_prescribed, report=report, next_visit=next_visit_obj)
            db.session.add(v)
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
