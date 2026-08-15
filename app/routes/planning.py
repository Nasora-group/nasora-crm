from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.forms import PlanningForm, CSRFOnlyForm
from app.models import Planning, User, JOURS, STRUCTURE_SLUGS
from app.utils import roles_required, encode_planning_slot, decode_planning_slot

planning_bp = Blueprint("planning", __name__)


def _build_creneaux_from_form():
    """Lit les structures sélectionnées + noms précis postés dans le
    formulaire et les encode en JSON, un champ par créneau jour/moment."""
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
    return creneaux


@planning_bp.route("/visualiser_planning")
@login_required
@roles_required("commercial")
def visualiser():
    plannings = (
        Planning.query.filter_by(commercial_id=current_user.id)
        .order_by(Planning.date.desc())
        .all()
    )
    delete_form = CSRFOnlyForm()
    return render_template("visualiser_planning.html", plannings=plannings, delete_form=delete_form)


@planning_bp.route("/saisie_planning", methods=["GET", "POST"])
@login_required
@roles_required("commercial")
def saisie():
    formulaire = PlanningForm()

    if formulaire.validate_on_submit():
        nouveau_planning = Planning(
            commercial_id=current_user.id,
            date=formulaire.date.data,
            **_build_creneaux_from_form(),
        )
        db.session.add(nouveau_planning)
        db.session.commit()
        flash("Planning enregistré avec succès.", "success")
        return redirect(url_for("planning.visualiser"))

    return render_template("saisie_planning.html", formulaire=formulaire, mode="create", existing_types={}, existing_details={})


@planning_bp.route("/planning/<int:planning_id>/modifier", methods=["GET", "POST"])
@login_required
@roles_required("commercial")
def edit_planning(planning_id):
    planning = Planning.query.get_or_404(planning_id)
    if planning.commercial_id != current_user.id:
        flash("Accès non autorisé : ce planning ne t'appartient pas.", "error")
        return render_template("403.html"), 403

    formulaire = PlanningForm(obj=planning)

    if formulaire.validate_on_submit():
        planning.date = formulaire.date.data
        for champ, valeur in _build_creneaux_from_form().items():
            setattr(planning, champ, valeur)
        db.session.commit()
        flash("Planning mis à jour avec succès.", "success")
        return redirect(url_for("planning.visualiser"))

    existing_types = {}
    existing_details = {}
    for jour in JOURS:
        for moment in ("matin", "soir"):
            champ = f"{jour}_{moment}"
            entries = decode_planning_slot(getattr(planning, champ))
            existing_types[champ] = [t for t, _n in entries]
            existing_details[champ] = {t: n for t, n in entries}

    return render_template(
        "saisie_planning.html",
        formulaire=formulaire,
        mode="edit",
        planning=planning,
        existing_types=existing_types,
        existing_details=existing_details,
    )


@planning_bp.route("/planning/<int:planning_id>/supprimer", methods=["POST"])
@login_required
@roles_required("commercial")
def delete_planning(planning_id):
    form = CSRFOnlyForm()
    planning = Planning.query.get_or_404(planning_id)

    if planning.commercial_id != current_user.id:
        flash("Accès non autorisé : ce planning ne t'appartient pas.", "error")
        return redirect(url_for("planning.visualiser"))

    if form.validate_on_submit():
        db.session.delete(planning)
        db.session.commit()
        flash("Planning supprimé.", "success")

    return redirect(url_for("planning.visualiser"))


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
