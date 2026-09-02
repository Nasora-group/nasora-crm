from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.models import Evaluation, EVALUATION_MAX_TOTAL
from app.routes.evaluations import MOIS_LABELS
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
