import logging
from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.forms import EvaluationForm
from app.models import User, Prospection, Evaluation, EVALUATION_SECTIONS, EVALUATION_MAX_TOTAL
from app.utils import roles_required

logger = logging.getLogger(__name__)

evaluations_bp = Blueprint("evaluations", __name__)

MOIS_LABELS = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
    7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre",
}


def _visits_count(commercial_id, year, month):
    """Compte les visites (prospections) d'un commercial pour un mois donné.
    Filtré en Python plutôt qu'avec une fonction SQL (EXTRACT/strftime) pour
    rester portable entre SQLite (dev) et PostgreSQL (production)."""
    dates = [
        d for (d,) in db.session.query(Prospection.date)
        .filter(Prospection.commercial_id == commercial_id)
        .all()
    ]
    return sum(1 for d in dates if d.year == year and d.month == month)


@evaluations_bp.route("/admin/evaluations")
@login_required
@roles_required("admin")
def list_commercials():
    commerciaux = User.query.filter_by(role="commercial").order_by(User.project, User.username).all()
    return render_template("admin_evaluations_commerciaux.html", commerciaux=commerciaux)


@evaluations_bp.route("/admin/evaluations/<int:commercial_id>")
@login_required
@roles_required("admin")
def commercial_history(commercial_id):
    commercial = User.query.get_or_404(commercial_id)
    evaluations = (
        Evaluation.query.filter_by(commercial_id=commercial_id)
        .order_by(Evaluation.year.desc(), Evaluation.month.desc())
        .all()
    )
    today = date.today()
    return render_template(
        "admin_evaluations_history.html",
        commercial=commercial,
        evaluations=evaluations,
        mois_labels=MOIS_LABELS,
        current_year=today.year,
        current_month=today.month,
    )


@evaluations_bp.route("/admin/evaluations/<int:commercial_id>/<int:year>/<int:month>", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_evaluation(commercial_id, year, month):
    if month < 1 or month > 12:
        abort(404)
    commercial = User.query.get_or_404(commercial_id)
    if commercial.role != "commercial":
        abort(404)

    evaluation = Evaluation.query.filter_by(commercial_id=commercial_id, year=year, month=month).first()
    form = EvaluationForm(obj=evaluation)
    visits = _visits_count(commercial_id, year, month)

    if form.validate_on_submit():
        try:
            if not evaluation:
                evaluation = Evaluation(commercial_id=commercial_id, year=year, month=month)
                db.session.add(evaluation)

            for field_name, *_ in [item for _, _, items in EVALUATION_SECTIONS for item in items]:
                setattr(evaluation, field_name, getattr(form, field_name).data or 0)
            evaluation.points_forts = form.points_forts.data
            evaluation.axes_amelioration = form.axes_amelioration.data
            evaluation.objectifs_quantitatifs = form.objectifs_quantitatifs.data
            evaluation.objectifs_qualitatifs = form.objectifs_qualitatifs.data
            evaluation.evaluator_id = current_user.id

            db.session.commit()
            flash(f"Évaluation de {commercial.username} pour {MOIS_LABELS[month]} {year} enregistrée.", "success")
            logger.info("Évaluation %s/%s/%s enregistrée par %s (score %.1f/100)",
                        commercial.username, year, month, current_user.username, evaluation.total_score)
            return redirect(url_for("evaluations.commercial_history", commercial_id=commercial_id))
        except Exception:
            db.session.rollback()
            logger.exception("Erreur lors de l'enregistrement de l'évaluation")
            flash("Erreur lors de l'enregistrement de l'évaluation.", "error")

    return render_template(
        "admin_evaluation_form.html",
        form=form,
        commercial=commercial,
        year=year,
        month=month,
        mois_label=MOIS_LABELS[month],
        sections=EVALUATION_SECTIONS,
        max_total=EVALUATION_MAX_TOTAL,
        visits=visits,
        evaluation=evaluation,
    )


@evaluations_bp.route("/admin/classement")
@login_required
@roles_required("admin")
def classement():
    today = date.today()
    year = request.args.get("year", today.year, type=int)
    month = request.args.get("month", today.month, type=int)

    commerciaux = User.query.filter_by(role="commercial").order_by(User.username).all()
    rows = []
    for c in commerciaux:
        evaluation = Evaluation.query.filter_by(commercial_id=c.id, year=year, month=month).first()
        visits = _visits_count(c.id, year, month)
        rows.append({
            "commercial": c,
            "evaluation": evaluation,
            "score": evaluation.total_score if evaluation else None,
            "niveau": evaluation.niveau if evaluation else None,
            "visits": visits,
        })

    # Tri : la note (annotation KPI) est prioritaire sur le nombre de visites,
    # conformément à la grille d'évaluation. Seuls les commerciaux évalués ce
    # mois-ci sont classables (la note étant le critère prioritaire).
    evalues = sorted(
        [r for r in rows if r["evaluation"] is not None],
        key=lambda r: (r["score"], r["visits"]),
        reverse=True,
    )
    non_evalues = [r for r in rows if r["evaluation"] is None]

    return render_template(
        "admin_classement.html",
        evalues=evalues,
        non_evalues=non_evalues,
        year=year,
        month=month,
        mois_label=MOIS_LABELS[month],
        mois_labels=MOIS_LABELS,
    )


@evaluations_bp.route("/mes-evaluations")
@login_required
@roles_required("commercial")
def my_evaluations():
    evaluations = (
        Evaluation.query.filter_by(commercial_id=current_user.id)
        .order_by(Evaluation.year.desc(), Evaluation.month.desc())
        .all()
    )
    return render_template("commercial_evaluations.html", evaluations=evaluations, mois_labels=MOIS_LABELS)


@evaluations_bp.route("/mes-evaluations/<int:year>/<int:month>")
@login_required
@roles_required("commercial")
def my_evaluation_detail(year, month):
    evaluation = Evaluation.query.filter_by(
        commercial_id=current_user.id, year=year, month=month
    ).first_or_404()
    visits = _visits_count(current_user.id, year, month)
    return render_template(
        "commercial_evaluation_detail.html",
        evaluation=evaluation,
        sections=EVALUATION_SECTIONS,
        max_total=EVALUATION_MAX_TOTAL,
        mois_label=MOIS_LABELS[month],
        year=year,
        visits=visits,
    )
