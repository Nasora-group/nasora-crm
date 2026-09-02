from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user

from app.models import Evaluation, EVALUATION_MAX_TOTAL, EVALUATION_SECTIONS
from app.models_clients import ClientVisit
from app.routes.evaluations import MOIS_LABELS, _visits_count
from app.utils import roles_required

commercial_evaluations_bp = Blueprint("commercial_evaluations", __name__)


@commercial_evaluations_bp.route("/mes-evaluations")
@login_required
@roles_required("commercial")
def my_evaluations():
    evaluations = (
        Evaluation.query
        .filter_by(commercial_id=current_user.id)
        .order_by(Evaluation.year.desc(), Evaluation.month.desc())
        .all()
    )
    return render_template(
        "commercial_evaluations.html",
        evaluations=evaluations,
        mois_labels=MOIS_LABELS,
        max_total=EVALUATION_MAX_TOTAL,
    )


@commercial_evaluations_bp.route("/mes-evaluations/<int:year>/<int:month>")
@login_required
@roles_required("commercial")
def my_evaluation_detail(year, month):
    if month < 1 or month > 12:
        abort(404)
    evaluation = Evaluation.query.filter_by(
        commercial_id=current_user.id,
        year=year,
        month=month,
    ).first_or_404()
    return render_template(
        "commercial_evaluation_detail.html",
        evaluation=evaluation,
        year=year,
        month=month,
        mois_label=MOIS_LABELS[month],
        max_total=EVALUATION_MAX_TOTAL,
        sections=EVALUATION_SECTIONS,
        visits=_visits_count(current_user.id, year, month),
    )
