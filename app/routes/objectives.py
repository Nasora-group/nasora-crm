import logging
from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required

from app.extensions import db
from app.forms import ObjectiveForm
from app.models import SalesObjective, SUPPLIERS
from app.utils import roles_required
from app.audit_log import audit

logger = logging.getLogger(__name__)

objectives_bp = Blueprint("objectives", __name__, url_prefix="/admin/objectifs")

MONTH_FIELDS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
DIVISION_LABELS = {"nasderm": "NASDERM", "nasmedic": "NASMEDIC"}


def _valid_division_or_404(division):
    if division not in DIVISION_LABELS:
        abort(404)
    return division


@objectives_bp.route("/<division>", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_objectives(division):
    _valid_division_or_404(division)
    year = request.args.get("year", type=int) or date.today().year

    form = ObjectiveForm()

    if form.validate_on_submit():
        try:
            # Objectif annuel
            _upsert_objective(division, year, None, form.annual_target.data)
            # Objectifs mensuels
            for month_index, field_name in enumerate(MONTH_FIELDS, start=1):
                value = getattr(form, field_name).data
                _upsert_objective(division, year, month_index, value)

            db.session.commit()
            audit(
                "objectives.update",
                target=f"{DIVISION_LABELS[division]}:{year}",
                details="annual_and_monthly_targets_updated",
            )
            flash(f"Objectifs {DIVISION_LABELS[division]} {year} enregistrés.", "success")
            logger.info("Objectifs %s %s mis à jour", division, year)
            return redirect(url_for("objectives.edit_objectives", division=division, year=year))
        except Exception:
            db.session.rollback()
            audit(
                "objectives.update",
                target=f"{DIVISION_LABELS[division]}:{year}",
                outcome="failure",
                details="transaction_rolled_back",
            )
            logger.exception("Erreur lors de l'enregistrement des objectifs")
            flash("Erreur lors de l'enregistrement des objectifs.", "error")

    elif request.method == "GET":
        existing = {
            o.month: o.target_amount
            for o in SalesObjective.query.filter_by(division=division, year=year).all()
        }
        form.annual_target.data = existing.get(None)
        for month_index, field_name in enumerate(MONTH_FIELDS, start=1):
            getattr(form, field_name).data = existing.get(month_index)

    return render_template(
        "admin_objectives.html",
        form=form,
        division=division,
        division_label=DIVISION_LABELS[division],
        year=year,
        month_fields=MONTH_FIELDS,
    )


def _upsert_objective(division, year, month, target_amount):
    if target_amount is None:
        # Champ laissé vide : on supprime l'objectif existant s'il y en avait un
        SalesObjective.query.filter_by(division=division, year=year, month=month).delete()
        return

    obj = SalesObjective.query.filter_by(division=division, year=year, month=month).first()
    if obj:
        obj.target_amount = target_amount
    else:
        db.session.add(SalesObjective(division=division, year=year, month=month, target_amount=target_amount))
