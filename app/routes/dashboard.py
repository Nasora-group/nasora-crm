import logging

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.forms import ProspectionForm
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
