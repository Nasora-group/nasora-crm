import io
import logging
from datetime import date

import pandas as pd
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, send_file
from flask_login import login_required, current_user
from sqlalchemy import func
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, KeepTogether
from reportlab.lib.units import mm

from app.extensions import db
from app.forms import EvaluationForm
from app.models import User, Prospection, Evaluation, EVALUATION_SECTIONS, EVALUATION_MAX_TOTAL
from app.models_clients import ClientVisit
from app.utils import roles_required

logger = logging.getLogger(__name__)
evaluations_bp = Blueprint("evaluations", __name__)

MOIS_LABELS = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
    7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre",
}


def _visits_count(commercial_id, year, month):
    """Nombre de visites métier uniques pour un commercial et un mois."""
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    month_start = date(year, month, 1)

    unique_visits = (
        db.session.query(ClientVisit.commercial_id, ClientVisit.client_id, ClientVisit.date)
        .filter(
            ClientVisit.commercial_id == commercial_id,
            ClientVisit.date >= month_start,
            ClientVisit.date < next_month,
            ClientVisit.is_duplicate.is_(False),
        )
        .distinct()
        .subquery()
    )
    return db.session.query(func.count()).select_from(unique_visits).scalar() or 0


def _evaluation_dashboard_data(commercial_id, year, month):
    evaluations = (
        Evaluation.query.filter_by(commercial_id=commercial_id)
        .order_by(Evaluation.year.desc(), Evaluation.month.desc())
        .all()
    )
    current = next((e for e in evaluations if e.year == year and e.month == month), None)
    previous = None
    if current:
        previous = next((e for e in evaluations if (e.year, e.month) < (current.year, current.month)), None)

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
        commercial=commercial, evaluations=evaluations, mois_labels=MOIS_LABELS,
        current_year=year, current_month=month, current_evaluation=current,
        previous_evaluation=previous, score_delta=delta, chart_points=chart_points,
        visits=visits, max_total=EVALUATION_MAX_TOTAL,
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
            logger.info("Évaluation %s/%s/%s enregistrée par %s (score %.1f/100)", commercial.username, year, month, current_user.username, evaluation.total_score)
            return redirect(url_for("evaluations.commercial_history", commercial_id=commercial_id, year=year, month=month))
        except Exception:
            db.session.rollback()
            logger.exception("Erreur lors de l'enregistrement de l'évaluation")
            flash("Erreur lors de l'enregistrement de l'évaluation.", "error")
    return render_template(
        "admin_evaluation_form.html", form=form, commercial=commercial, year=year, month=month,
        mois_label=MOIS_LABELS[month], sections=EVALUATION_SECTIONS, max_total=EVALUATION_MAX_TOTAL,
        visits=visits, evaluation=evaluation,
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
        rows.append({"commercial": c, "evaluation": evaluation, "score": evaluation.total_score if evaluation else None, "niveau": evaluation.niveau if evaluation else None, "visits": visits})
    evalues = sorted([r for r in rows if r["evaluation"] is not None], key=lambda r: (r["score"], r["visits"]), reverse=True)
    non_evalues = [r for r in rows if r["evaluation"] is None]
    average = round(sum(r["score"] for r in evalues) / len(evalues), 1) if evalues else None
    excellent_count = sum(1 for r in evalues if r["niveau"] == "Excellent")
    bon_count = sum(1 for r in evalues if r["niveau"] == "Bon")
    return render_template(
        "admin_classement.html", evalues=evalues, non_evalues=non_evalues, year=year, month=month,
        mois_label=MOIS_LABELS[month], mois_labels=MOIS_LABELS, average=average,
        excellent_count=excellent_count, bon_count=bon_count,
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


def _pdf_header(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#4a6741"))
    canvas.setLineWidth(1)
    canvas.line(15 * mm, 14 * mm, 282 * mm, 14 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawString(15 * mm, 9 * mm, "NASORA Health & Skincare — CRM interne")
    canvas.drawRightString(282 * mm, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


@evaluations_bp.route("/admin/evaluations/<int:commercial_id>/export.pdf")
@login_required
@roles_required("admin")
def export_evaluations_pdf(commercial_id):
    commercial = User.query.get_or_404(commercial_id)
    evaluations = Evaluation.query.filter_by(commercial_id=commercial_id).order_by(Evaluation.year, Evaluation.month).all()

    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=landscape(A4), rightMargin=15 * mm, leftMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=20 * mm,
        title=f"Rapport d'évaluation — {commercial.username}",
        author="NASORA Health & Skincare",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=colors.HexColor("#35502f"), alignment=TA_LEFT, spaceAfter=3)
    subtitle = ParagraphStyle("ReportSubtitle", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#666666"), spaceAfter=10)
    section = ParagraphStyle("Section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.HexColor("#35502f"), spaceBefore=8, spaceAfter=5)
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=7.5, leading=10)
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=8.5, leading=11)

    story = []
    logo_path = "app/static/images/logo.jpg"
    try:
        logo = Image(logo_path, width=38 * mm, height=18 * mm)
        logo.hAlign = "LEFT"
        header = Table([[logo, Paragraph("RAPPORT D’ÉVALUATION COMMERCIALE", title)]], colWidths=[45 * mm, 222 * mm])
        header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        story.append(header)
    except Exception:
        story.append(Paragraph("NASORA HEALTH & SKINCARE", title))
    story.append(Paragraph(f"Fiche complète de suivi — <b>{commercial.username}</b>", subtitle))

    profile = [
        [Paragraph("Commercial", small), Paragraph("Division", small), Paragraph("Zone", small), Paragraph("Nombre d’évaluations", small)],
        [Paragraph(str(commercial.username), body), Paragraph(str(getattr(commercial, "project", "—") or "—"), body), Paragraph(str(getattr(commercial, "zone", "—") or "—"), body), Paragraph(str(len(evaluations)), body)],
    ]
    profile_table = Table(profile, colWidths=[70 * mm, 55 * mm, 55 * mm, 42 * mm])
    profile_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8efe5")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#35502f")), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b9c5b5")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("PADDING", (0, 0), (-1, -1), 6)]))
    story += [profile_table, Spacer(1, 8)]

    if not evaluations:
        story.append(Paragraph("Aucune évaluation enregistrée pour ce commercial.", body))
    else:
        for e in evaluations:
            story.append(Paragraph(f"{MOIS_LABELS[e.month]} {e.year} — Score global : {e.total_score:.1f}/{EVALUATION_MAX_TOTAL} — {e.niveau}", section))
            summary = [
                ["Score global", "Niveau", "Visites métier", "Évaluateur", "Date du rapport"],
                [f"{e.total_score:.1f}/{EVALUATION_MAX_TOTAL}", e.niveau or "—", str(_visits_count(commercial_id, e.year, e.month)), e.evaluator.username if e.evaluator else "—", date.today().strftime("%d/%m/%Y")],
            ]
            st = Table(summary, colWidths=[40 * mm, 45 * mm, 40 * mm, 55 * mm, 45 * mm])
            st.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a6741")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b9c5b5")), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("PADDING", (0, 0), (-1, -1), 5)]))
            story.append(st)

            section_data = [["Rubrique / critère", "Note", "Maximum"]]
            for section_name, section_desc, items in EVALUATION_SECTIONS:
                section_data.append([Paragraph(f"<b>{section_name}</b><br/><font size='6'>{section_desc or ''}</font>", small), "", ""])
                section_total = 0
                section_max = 0
                for field_name, label, max_pts, _ in items:
                    value = getattr(e, field_name) or 0
                    section_total += value
                    section_max += max_pts
                    section_data.append([Paragraph(label, small), f"{value:g}", f"{max_pts:g}"])
                section_data.append([Paragraph(f"<b>Total {section_name}</b>", small), f"{section_total:g}", f"{section_max:g}"])
            details = Table(section_data, colWidths=[205 * mm, 30 * mm, 30 * mm], repeatRows=1)
            details.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a6741")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a6741")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c7cec4")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(details)

            narrative = [
                [Paragraph("Points forts", section), Paragraph("Axes d’amélioration", section)],
                [Paragraph((e.points_forts or "Aucun point fort renseigné.").replace("\n", "<br/>"), body), Paragraph((e.axes_amelioration or "Aucun axe d’amélioration renseigné.").replace("\n", "<br/>"), body)],
                [Paragraph("Objectifs quantitatifs", section), Paragraph("Objectifs qualitatifs", section)],
                [Paragraph((e.objectifs_quantitatifs or "Aucun objectif quantitatif renseigné.").replace("\n", "<br/>"), body), Paragraph((e.objectifs_qualitatifs or "Aucun objectif qualitatif renseigné.").replace("\n", "<br/>"), body)],
            ]
            nt = Table(narrative, colWidths=[132 * mm, 132 * mm])
            nt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c7cec4")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f6f1")), ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#f3f6f1")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
            story.append(nt)
            story.append(Spacer(1, 10))

    doc.build(story, onFirstPage=_pdf_header, onLaterPages=_pdf_header)
    output.seek(0)
    filename = f"rapport_evaluation_{commercial.username}_{date.today().isoformat()}.pdf"
    return send_file(output, as_attachment=True, download_name=filename, mimetype="application/pdf")


@evaluations_bp.route("/mes-evaluations")
@login_required
@roles_required("commercial")
def my_evaluations():
    evaluations = Evaluation.query.filter_by(commercial_id=current_user.id).order_by(Evaluation.year.desc(), Evaluation.month.desc()).all()
    return render_template("commercial_evaluations.html", evaluations=evaluations, mois_labels=MOIS_LABELS)


@evaluations_bp.route("/mes-evaluations/<int:year>/<int:month>")
@login_required
@roles_required("commercial")
def my_evaluation_detail(year, month):
    evaluation = Evaluation.query.filter_by(commercial_id=current_user.id, year=year, month=month).first_or_404()
    visits = _visits_count(current_user.id, year, month)
    return render_template(
        "commercial_evaluation_detail.html", evaluation=evaluation, sections=EVALUATION_SECTIONS,
        max_total=EVALUATION_MAX_TOTAL, mois_label=MOIS_LABELS[month], year=year, visits=visits,
    )
