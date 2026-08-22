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
    owned = Client.owner_id == current_user.id
    visited = Client.id.in_(db.session.query(ClientVisit.client_id).filter(ClientVisit.commercial_id == current_user.id))
    return Client.query.filter(or_(owned, Client.owner_id.is_(None), visited))


def _commercial_can_access_client(client):
    if current_user.role != "commercial":
        return True
    return client.owner_id in (None, current_user.id) or ClientVisit.query.filter_by(client_id=client.id, commercial_id=current_user.id).first() is not None


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
            potential = max(1, min(5, int(request.form.get("potential", 3))))
            owner_id = current_user.id if current_user.role == "commercial" else (request.form.get("owner_id", type=int) or None)
            c = Client(name=request.form.get("name", "").strip(), specialty=request.form.get("specialty", "").strip() or None, structure=request.form.get("structure", "").strip(), establishment=request.form.get("establishment", "").strip() or None, phone=request.form.get("phone", "").strip() or None, email=request.form.get("email", "").strip() or None, zone=request.form.get("zone", "").strip() or None, address=request.form.get("address", "").strip() or None, potential=potential, notes=request.form.get("notes", "").strip() or None, owner_id=owner_id)
            if not c.name or not c.structure:
                flash("Le nom et la structure sont obligatoires.", "error")
                return render_template("client_form.html", client=c, structure_choices=[s[0] for s in STRUCTURES], commerciaux=User.query.filter_by(role="commercial", is_active_account=True).order_by(User.username).all())
            db.session.add(c); db.session.commit(); flash("Professionnel ajouté à la base CRM.", "success"); return redirect(url_for("clients.client_detail", client_id=c.id))
        except Exception:
            db.session.rollback(); flash("Impossible d'enregistrer le professionnel.", "error")
    return render_template("client_form.html", client=None, structure_choices=[s[0] for s in STRUCTURES], commerciaux=User.query.filter_by(role="commercial", is_active_account=True).order_by(User.username).all())


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
    if legacy_history and (not client.last_visit or legacy_history[0].date > client.last_visit):
        client.last_visit = legacy_history[0].date
        db.session.commit()
    latest_crm_next = next((v.next_visit for v in visits if v.next_visit), None)
    if latest_crm_next and (not client.next_visit or latest_crm_next != client.next_visit):
        client.next_visit = latest_crm_next
        db.session.commit()
    presented_count = sum(1 for v in visits if (v.products_presented or "").strip()) + sum(1 for v in legacy_history if (v.produits_presentes or "").strip())
    prescribed_count = sum(1 for v in visits if (v.products_prescribed or "").strip()) + sum(1 for v in legacy_history if (v.produits_prescrits or "").strip())
    return render_template("client_detail.html", client=client, history=legacy_history, visits=visits, presented_count=presented_count, prescribed_count=prescribed_count)


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
            v = ClientVisit(client_id=client.id, commercial_id=current_user.id, date=date.fromisoformat(visit_date), products_presented=request.form.get("products_presented", "").strip() or None, products_prescribed=request.form.get("products_prescribed", "").strip() or None, report=request.form.get("report", "").strip() or None, next_visit=date.fromisoformat(next_visit) if next_visit else None)
            db.session.add(v)
            client.last_visit = v.date
            client.next_visit = v.next_visit
            db.session.commit()
            flash("Visite enregistrée avec succès.", "success")
            return redirect(url_for("clients.client_detail", client_id=client.id))
        except Exception:
            db.session.rollback()
            flash("Impossible d'enregistrer la visite. Vérifiez les dates.", "error")
    return render_template("client_visit_form.html", client=client, today=date.today().isoformat())
