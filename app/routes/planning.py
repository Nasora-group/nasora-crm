from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.forms import PlanningForm
from app.models import Planning, User, JOURS, STRUCTURE_SLUGS
from app.utils import roles_required, encode_planning_slot

planning_bp = Blueprint("planning", __name__)


@planning_bp.route("/visualiser_planning")
@login_required
@roles_required("commercial")
def visualiser():
    plannings = (
        Planning.query.filter_by(commercial_id=current_user.id)
        .order_by(Planning.date.desc())
        .all()
    )
    return render_template("visualiser_planning.html", plannings=plannings)


@planning_bp.route("/saisie_planning", methods=["GET", "POST"])
@login_required
@roles_required("commercial")
def saisie():
    formulaire = PlanningForm()

    if formulaire.validate_on_submit():
        creneaux = {}
        for jour in JOURS:
            for moment in ("matin", "soir"):
                champ = f"{jour}_{moment}"
                structures_selectionnees = request.form.getlist(champ)
                entries = []
                for structure in structures_selectionnees:
                    slug = STRUCTURE_SLUGS.get(structure, structure.replace(" ", "_"))
                    nom = request.form.get(f"{champ}_nom__{slug}", "")
                    entries.append((structure, nom))
                creneaux[champ] = encode_planning_slot(entries)

        nouveau_planning = Planning(
            commercial_id=current_user.id,
            date=formulaire.date.data,
            **creneaux,
        )
        db.session.add(nouveau_planning)
        db.session.commit()
        flash("Planning enregistré avec succès.", "success")
        return redirect(url_for("planning.visualiser"))

    return render_template("saisie_planning.html", formulaire=formulaire)


@planning_bp.route("/admin_plannings")
@login_required
@roles_required("admin")
def admin_plannings():
    commerciaux = User.query.filter_by(role="commercial").order_by(User.username).all()
    return render_template("admin_plannings.html", commerciaux=commerciaux)


@planning_bp.route("/admin_planning_detail/<int:commercial_id>")
@login_required
@roles_required("admin")
def admin_planning_detail(commercial_id):
    commercial = User.query.get_or_404(commercial_id)
    plannings = (
        Planning.query.filter_by(commercial_id=commercial_id)
        .order_by(Planning.date.desc())
        .all()
    )
    return render_template("admin_planning_detail.html", plannings=plannings, commercial=commercial)
