import logging

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.forms import ProspectionForm, CSRFOnlyForm
from app.models import Prospection, get_active_products_for_division
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
            )
            db.session.add(prospection)
            db.session.flush()
            saved_id = prospection.id
            db.session.commit()
            logger.info("Prospection #%s enregistrée par %s", saved_id, current_user.username)
            flash("Prospection enregistrée avec succès.", "success")
            return redirect(url_for("dashboard.index"))
        except Exception:
            db.session.rollback()
            logger.exception("Erreur lors de l'enregistrement d'une prospection pour %s", current_user.username)
            flash("Impossible d'enregistrer la prospection. Vérifiez les données et réessayez.", "error")
            return _render_dashboard(form)

    return _render_dashboard(form)


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
