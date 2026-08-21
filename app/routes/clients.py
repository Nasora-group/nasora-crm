from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from app.extensions import db
from app.models import User, Prospection, STRUCTURES
from app.models_clients import Client, ClientVisit
from app.utils import roles_required

clients_bp = Blueprint("clients", __name__)

@clients_bp.route("/admin/clients")
@login_required
@roles_required("admin", "commercial")
def list_clients():
    q = (request.args.get("q") or "").strip(); structure = (request.args.get("structure") or "").strip(); potential = (request.args.get("potential") or "").strip()
    query = Client.query
    if current_user.role == "commercial": query = query.filter(or_(Client.owner_id == current_user.id, Client.owner_id.is_(None)))
    if q:
        term = f"%{q}%"; query = query.filter(or_(Client.name.ilike(term), Client.establishment.ilike(term), Client.phone.ilike(term), Client.zone.ilike(term)))
    if structure: query = query.filter(Client.structure == structure)
    if potential: query = query.filter(Client.potential == int(potential))
    page = request.args.get("page", 1, type=int); pagination = query.order_by(Client.name.asc()).paginate(page=page, per_page=25, error_out=False)
    total = query.count(); structures = db.session.query(func.count(func.distinct(Client.structure))).scalar() or 0; high_potential = query.filter(Client.potential >= 4).count()
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
    if current_user.role == "commercial" and client.owner_id not in (None, current_user.id): return render_template("403.html"), 403
    if client.phone: visit_query = Prospection.query.filter(or_(Prospection.nom_client.ilike(client.name), Prospection.telephone == client.phone))
    else: visit_query = Prospection.query.filter(Prospection.nom_client.ilike(client.name))
    if current_user.role == "commercial": visit_query = visit_query.filter(Prospection.commercial_id == current_user.id)
    legacy_history = visit_query.order_by(Prospection.date.desc()).all()
    visits = ClientVisit.query.filter_by(client_id=client.id)
    if current_user.role == "commercial": visits = visits.filter(ClientVisit.commercial_id == current_user.id)
    visits = visits.order_by(ClientVisit.date.desc()).all()
    if legacy_history and not client.last_visit: client.last_visit = legacy_history[0].date; db.session.commit()
    presented_count = sum(1 for v in visits if (v.products_presented or "").strip()) + sum(1 for v in legacy_history if (v.produits_presentes or "").strip())
    prescribed_count = sum(1 for v in visits if (v.products_prescribed or "").strip()) + sum(1 for v in legacy_history if (v.produits_prescrits or "").strip())
    return render_template("client_detail.html", client=client, history=legacy_history, visits=visits, presented_count=presented_count, prescribed_count=prescribed_count)

@clients_bp.route("/admin/clients/<int:client_id>/visits/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "commercial")
def new_visit(client_id):
    client = Client.query.get_or_404(client_id)
    if current_user.role == "commercial" and client.owner_id not in (None, current_user.id): return render_template("403.html"), 403
    if request.method == "POST":
        try:
            visit_date = request.form.get("date") or date.today().isoformat()
            next_visit = request.form.get("next_visit") or None
            v = ClientVisit(client_id=client.id, commercial_id=current_user.id, date=date.fromisoformat(visit_date), products_presented=request.form.get("products_presented", "").strip() or None, products_prescribed=request.form.get("products_prescribed", "").strip() or None, report=request.form.get("report", "").strip() or None, next_visit=date.fromisoformat(next_visit) if next_visit else None)
            db.session.add(v); client.last_visit=v.date; client.next_visit=v.next_visit; db.session.commit(); flash("Visite enregistrée avec succès.", "success"); return redirect(url_for("clients.client_detail", client_id=client.id))
        except Exception:
            db.session.rollback(); flash("Impossible d'enregistrer la visite. Vérifiez les dates.", "error")
    return render_template("client_visit_form.html", client=client, today=date.today().isoformat())
