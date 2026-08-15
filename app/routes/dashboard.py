import logging

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.forms import ProspectionForm, CSRFOnlyForm
from app.models import Prospection
from app.utils import roles_required

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard", methods=["GET", "POST"])
@login_required
@roles_required("commercial")
def index():
    form = ProspectionForm()
    if form.validate_on_submit():
        try:
            prospection = Prospection(
                commercial_id=current_user.id,
                date=form.date.data,
                nom_client=form.nom_client.data,
                specialite=form.specialite.data,
                structure=form.structure.data,
                telephone=form.telephone.data,
                profils_prospect=form.profils_prospect.data,
                produits_presentes=form.produits_presentes.data,
                produits_prescrits=form.produits_prescrits.data,
            )
            db.session.add(prospection)
            db.session.commit()
            flash("Données enregistrées avec succès", "success")
            logger.info("Prospection enregistrée par %s", current_user.username)
        except Exception:
            db.session.rollback()
            flash("Erreur lors de l'enregistrement des données.", "error")
            logger.exception("Erreur lors de l'enregistrement d'une prospection")
        return redirect(url_for("dashboard.index"))

    return render_template("dashboard.html", form=form)


@dashboard_bp.route("/dashboard/prospection/<int:prospection_id>/modifier", methods=["GET", "POST"])
@login_required
@roles_required("commercial")
def edit_prospection(prospection_id):
    prospection = Prospection.query.get_or_404(prospection_id)
    if prospection.commercial_id != current_user.id:
        flash("Accès non autorisé : cette prospection ne t'appartient pas.", "error")
        return render_template("403.html"), 403

    form = ProspectionForm(obj=prospection)

    if form.validate_on_submit():
        try:
            prospection.date = form.date.data
            prospection.nom_client = form.nom_client.data
            prospection.specialite = form.specialite.data
            prospection.structure = form.structure.data
            prospection.telephone = form.telephone.data
            prospection.profils_prospect = form.profils_prospect.data
            prospection.produits_presentes = form.produits_presentes.data
            prospection.produits_prescrits = form.produits_prescrits.data
            db.session.commit()
            flash("Prospection mise à jour avec succès.", "success")
            logger.info("Prospection #%s modifiée par %s", prospection_id, current_user.username)
            return redirect(url_for("admin.commercial_detail", username=current_user.username))
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
        return redirect(url_for("admin.commercial_detail", username=current_user.username))

    if form.validate_on_submit():
        db.session.delete(prospection)
        db.session.commit()
        flash("Prospection supprimée.", "success")
        logger.info("Prospection #%s supprimée par %s", prospection_id, current_user.username)

    return redirect(url_for("admin.commercial_detail", username=current_user.username))
