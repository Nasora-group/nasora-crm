import io
import logging
from datetime import date

import pandas as pd
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, send_file
from flask_login import login_required, current_user
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

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
    dates = [
        d for (d,) in db.session.query(Prospection.date)
        .filter(Prospection.commercial_id == commercial_id)
        .all()
    ]
    return sum(1 for d in dates if d.year == year and d.month == month)


def _evaluation_dashboard_data(commercial_id, year, month):
    evaluations = (
        Evaluation.query.filter_by(commercial_id=commercial_id)
        .order_by(Evaluation.year.desc(), Evaluation.month.desc())
        .all()
    )
    current = next((e for e in evaluations if e.year == year and e.month == month), None)
    previous = None
    if current:
        previous = next(
            (e for e in evaluations if (e.year, e.month) < (current.year, current.month)),
            None,
        )

    # 12 derniers mois glissants, avec une série continue même en l'absence d'évaluation.
    points = []
    y, m = year, month
    for _ in range(12):
        evaluation = next((e for e in evaluations if e.year == y and e.month == m), None)
        points.append({
            "label": f"{MOIS_LABELS[m][:3]} {str(y)[2:]}",
            "score": round(evaluation.total_score, 1) if evaluation else None,
            "year": y,
            "month": m,
        })
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    points.reverse()

    visits = _visits_count(commercial_id, year, month)
    return evaluations, current, previous, points, visits


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
    today = date.today()
    year = request.args.get("year", today.year, type=int)
    month = request.args.get("month", today.month, type=int)
    if month < 1 or month > 12:
        month = today.month

    evaluations, current, previous, chart_points, visits = _evaluation_dashboard_data(commercial_id, year, month)
    delta = round(current.total_score - previous.total_score, 1) if current and previous else None

    return render_template(
        "admin_evaluations_history.html",
        commercial=commercial,
        evaluations=evaluations,
        mois_labels=MOIS_LABELS,
        current_year=year,
        current_month=month,
        current_evaluation=current,
        previous_evaluation=previous,
        score_delta=delta,
        chart_points=chart_points,
        visits=visits,
        max_total=EVALUATION_MAX_TOTAL,
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
            logger.info(
                "Évaluation %s/%s/%s enregistrée par %s (score %.1f/100)",
                commercial.username, year, month, current_user.username, evaluation.total_score,
            )
            return redirect(url_for("evaluations.commercial_history", commercial_id=commercial_id, year=year, month=month))
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

    evalues = sorted(
        [r for r in rows if r["evaluation"] is not None],
        key=lambda r: (r["score"], r["visits"]),
        reverse=True,
    )
    non_evalues = [r for r in rows if r["evaluation"] is None]
    average = round(sum(r["score"] for r in evalues) / len(evalues), 1) if evalues else None
    excellent_count = sum(1 for r in evalues if r["niveau"] == "Excellent")
    bon_count = sum(1 for r in evalues if r["niveau"] == "Bon")

    return render_template(
        "admin_classement.html",
        evalues=evalues,
        non_evalues=non_evalues,
        year=year,
        month=month,
        mois_label=MOIS_LABELS[month],
        mois_labels=MOIS_LABELS,
        average=average,
        excellent_count=excellent_count,
        bon_count=bon_count,
    )


@evaluations_bp.route("/admin/evaluations/<int:commercial_id>/export.xlsx")
@login_required
@roles_required("admin")
def export_evaluations_excel(commercial_id):
    commercial = User.query.get_or_404(commercial_id)
    evaluations = Evaluation.query.filter_by(commercial_id=commercial_id).order_by(Evaluation.year, Evaluation.month).all()

    rows = []
    for e in evaluations:
        row = {
            "Mois": f"{MOIS_LABELS[e.month]} {e.year}",
            "Score total": round(e.total_score, 1),
            "Niveau": e.niveau,
            "Évalué par": e.evaluator.username if e.evaluator else "",
            "Visites": _visits_count(commercial_id, e.year, e.month),
        }
        for field_name, label, max_pts, _ in [item for _, _, items in EVALUATION_SECTIONS for item in items]:
            row[label] = getattr(e, field_name) or 0
        rows.append(row)

    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Evaluations")
        worksheet = writer.sheets["Evaluations"]
        worksheet.freeze_panes(1, 0)
        worksheet.autofilter(0, 0, max(len(df), 1), max(len(df.columns) - 1, 0))
        for idx, col in enumerate(df.columns):
            width = min(max(len(str(col)) + 2, 12), 35)
            worksheet.set_column(idx, idx, width)
    output.seek(0)
    filename = f"evaluations_{commercial.username}_{date.today().isoformat()}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@evaluations_bp.route("/admin/evaluations/<int:commercial_id>/export.pdf")
@login_required
@roles_required("admin")
def export_evaluations_pdf(commercial_id):
    commercial = User.query.get_or_404(commercial_id)
    evaluations = Evaluation.query.filter_by(commercial_id=commercial_id).order_by(Evaluation.year, Evaluation.month).all()

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    story = [Paragraph(f"Historique des évaluations KPI — {commercial.username}", styles["Title"]), Spacer(1, 10)]
    data = [["Mois", "Score /100", "Niveau", "Visites", "Évaluateur"]]
    for e in evaluations:
        data.append([
            f"{MOIS_LABELS[e.month]} {e.year}",
            f"{e.total_score:.1f}",
            e.niveau,
            str(_visits_count(commercial_id, e.year, e.month)),
            e.evaluator.username if e.evaluator else "—",
        ])
    if len(data) == 1:
        data.append(["Aucune évaluation", "—", "—", "—", "—"])

    table = Table(data, repeatRows=1, colWidths=[150, 90, 100, 70, 140])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a6741")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6f1")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(table)
    doc.build(story)
    output.seek(0)
    filename = f"evaluations_{commercial.username}_{date.today().isoformat()}.pdf"
    return send_file(output, as_attachment=True, download_name=filename, mimetype="application/pdf")


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
