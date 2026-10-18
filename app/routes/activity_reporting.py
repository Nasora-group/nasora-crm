import csv
import io
from collections import Counter
from datetime import date, timedelta

from flask import Blueprint, Response, render_template, request, send_file
from flask_login import login_required

from app.models import AnimationSale, DIVISION_SUPPLIERS, Planning, Prospection, User
from app.utils import decode_planning_slot, roles_required
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

activity_reporting_bp = Blueprint("activity_reporting", __name__)


def _csv_response(filename, headers, rows):
    """Build a UTF-8 CSV response that opens cleanly in spreadsheet software."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(headers)
    writer.writerows(rows)
    response = Response("\ufeff" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _parse_day(value, fallback):
    try:
        return date.fromisoformat(value) if value else fallback
    except (TypeError, ValueError):
        return fallback


def _planned_entry_count(raw):
    """Count individual establishments, including comma-separated names."""
    count = 0
    for _structure, name in decode_planning_slot(raw):
        names = [item.strip() for item in (name or "").split(",") if item.strip()]
        count += len(names) if names else 1
    return count


def _prospection_counts(rows):
    """Separate all recorded visits from visits linked to a planning slot."""
    all_by_user = Counter()
    all_by_day = Counter()
    linked_by_user = Counter()
    linked_by_day = Counter()
    outside_by_user = Counter()
    outside_by_day = Counter()
    for row in rows:
        all_by_user[row.commercial_id] += 1
        all_by_day[row.date] += 1
        if row.planning_id is None:
            outside_by_user[row.commercial_id] += 1
            outside_by_day[row.date] += 1
        else:
            linked_by_user[row.commercial_id] += 1
            linked_by_day[row.date] += 1
    return {
        "all_by_user": all_by_user,
        "all_by_day": all_by_day,
        "linked_by_user": linked_by_user,
        "linked_by_day": linked_by_day,
        "outside_by_user": outside_by_user,
        "outside_by_day": outside_by_day,
    }


def _execution_rate(planned, linked_prospections):
    """Return execution based only on prospections linked to a planning."""
    return round(linked_prospections * 100 / planned, 1) if planned else None


@activity_reporting_bp.route("/admin/rapport-activite")
@login_required
@roles_required("admin")
def index():
    today = date.today()
    end_day = _parse_day(request.args.get("date_to"), today)
    start_day = _parse_day(request.args.get("date_from"), end_day - timedelta(days=6))
    if start_day > end_day:
        start_day = end_day - timedelta(days=6)
    # Keep report queries bounded for predictable performance.
    if (end_day - start_day).days > 89:
        start_day = end_day - timedelta(days=89)
    end_exclusive = end_day + timedelta(days=1)

    division = (request.args.get("division") or "all").strip().lower()
    if division not in DIVISION_SUPPLIERS:
        division = "all"
    division_filter = None if division == "all" else division

    users_query = User.query.filter(
        User.role.in_(("commercial", "animateur")),
        User.is_active_account.is_(True),
    )
    # A division filter must scope planning/prospections to the same team as
    # animation sales; otherwise the consolidated report mixes divisions.
    if division_filter:
        users_query = users_query.filter(User.project == division_filter)
    users = users_query.order_by(User.username).all()
    selected_raw = (request.args.get("commercial_id") or "").strip()
    selected_id = int(selected_raw) if selected_raw.isdigit() else None
    if selected_id and not any(user.id == selected_id for user in users):
        selected_id = None
    if selected_id:
        users = [user for user in users if user.id == selected_id]

    user_ids = [user.id for user in users]
    planned_by_user = Counter()
    planned_by_day = Counter()
    if user_ids:
        plans = Planning.query.filter(
            Planning.commercial_id.in_(user_ids),
            Planning.date >= start_day - timedelta(days=6),
            Planning.date <= end_day,
        ).all()
        weekday_fields = (
            ("lundi", 0), ("mardi", 1), ("mercredi", 2),
            ("jeudi", 3), ("vendredi", 4), ("samedi", 5), ("dimanche", 6),
        )
        for plan in plans:
            for field, offset in weekday_fields:
                planned_date = plan.date + timedelta(days=offset)
                if start_day <= planned_date <= end_day:
                    slots = _planned_entry_count(getattr(plan, field, None))
                    planned_by_user[plan.commercial_id] += slots
                    planned_by_day[planned_date] += slots

    prospection_by_user = Counter()
    prospection_by_day = Counter()
    planned_prospection_by_user = Counter()
    planned_prospection_by_day = Counter()
    hors_planning_by_user = Counter()
    hors_planning_by_day = Counter()
    if user_ids:
        prospections = Prospection.query.filter(
            Prospection.commercial_id.in_(user_ids),
            Prospection.date >= start_day,
            Prospection.date < end_exclusive,
        ).all()
        counts = _prospection_counts(prospections)
        prospection_by_user = counts["all_by_user"]
        prospection_by_day = counts["all_by_day"]
        planned_prospection_by_user = counts["linked_by_user"]
        planned_prospection_by_day = counts["linked_by_day"]
        hors_planning_by_user = counts["outside_by_user"]
        hors_planning_by_day = counts["outside_by_day"]

    animation_query = AnimationSale.query.filter(
        AnimationSale.animation_date >= start_day,
        AnimationSale.animation_date < end_exclusive,
    )
    if user_ids:
        animation_query = animation_query.filter(AnimationSale.animateur_id.in_(user_ids))
    else:
        animation_query = animation_query.filter(AnimationSale.animateur_id == -1)
    if division_filter:
        animation_query = animation_query.filter(AnimationSale.project == division_filter)
    animation_rows = animation_query.all()

    animation_lines_by_user = Counter()
    animation_ca_by_user = Counter()
    animation_lines_by_day = Counter()
    animation_ca_by_day = Counter()
    for row in animation_rows:
        amount = float(row.total_amount or 0)
        animation_lines_by_user[row.animateur_id] += 1
        animation_ca_by_user[row.animateur_id] += amount
        animation_lines_by_day[row.animation_date] += 1
        animation_ca_by_day[row.animation_date] += amount

    summary_rows = []
    for user in users:
        planned = planned_by_user[user.id] if user.role == "commercial" else 0
        prospect_count = prospection_by_user[user.id] if user.role == "commercial" else 0
        linked_prospect_count = planned_prospection_by_user[user.id] if user.role == "commercial" else 0
        outside_planning_count = hors_planning_by_user[user.id] if user.role == "commercial" else 0
        animation_lines = animation_lines_by_user[user.id] if user.role == "animateur" else 0
        animation_ca = animation_ca_by_user[user.id] if user.role == "animateur" else 0.0
        execution = _execution_rate(planned, linked_prospect_count)
        if user.role == "commercial":
            status = "warning" if planned and linked_prospect_count < planned else ("success" if prospect_count else "neutral")
            status_text = "À vérifier" if status == "warning" else ("Saisies enregistrées" if prospect_count else "Aucune prospection")
        else:
            status = "success" if animation_lines else "neutral"
            status_text = "Animations saisies" if animation_lines else "Aucune vente d’animation"
        summary_rows.append({
            "id": user.id,
            "name": user.username,
            "role": "Visiteur médical" if user.role == "commercial" else "Animateur(trice)",
            "planned": planned,
            "prospections": prospect_count,
            "hors_planning": outside_planning_count,
            "execution": execution,
            "animation_lines": animation_lines,
            "animation_ca": animation_ca,
            "status": status,
            "status_text": status_text,
        })

    daily_rows = []
    day = start_day
    while day <= end_day:
        daily_rows.append({
            "date": day,
            "planned": planned_by_day[day],
            "prospections": prospection_by_day[day],
            "planned_prospections": planned_prospection_by_day[day],
            "hors_planning": hors_planning_by_day[day],
            "animation_lines": animation_lines_by_day[day],
            "animation_ca": animation_ca_by_day[day],
        })
        day += timedelta(days=1)

    total_planned = sum(row["planned"] for row in summary_rows)
    total_prospections = sum(row["prospections"] for row in summary_rows)
    total_linked_prospections = sum(row["prospections"] - row["hors_planning"] for row in summary_rows)
    total_animation_lines = sum(row["animation_lines"] for row in summary_rows)
    total_animation_ca = sum(row["animation_ca"] for row in summary_rows)
    execution_pct = _execution_rate(total_planned, total_linked_prospections)

    export_type = request.args.get("export")
    if export_type == "pdf":
        # Génération en mémoire : aucune donnée métier n'est modifiée ni stockée.
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer, pagesize=landscape(A4),
            rightMargin=12 * mm, leftMargin=12 * mm,
            topMargin=12 * mm, bottomMargin=12 * mm,
            title="Rapport hebdomadaire NASORA CRM",
            author="NASORA CRM",
        )
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name="NasoraSubtitle", parent=styles["Normal"],
            fontSize=8, leading=11, textColor=colors.HexColor("#5f6f65"),
        ))
        story = [
            Paragraph("NASORA CRM - RAPPORT CONSOLIDÉ D’ACTIVITÉ", styles["Title"]),
            Paragraph(
                f"Période : {start_day.strftime('%d/%m/%Y')} au {end_day.strftime('%d/%m/%Y')} "
                f"| Division animation : {division.upper() if division != 'all' else 'TOUTES'}",
                styles["NasoraSubtitle"],
            ),
            Spacer(1, 5 * mm),
            Paragraph("Indicateurs clés", styles["Heading2"]),
        ]
        kpi_data = [[
            "Créneaux planifiés", "Prospections saisies", "Exécution planning",
            "Lignes animation", "CA animation (FCFA)",
        ], [
            str(total_planned), str(total_prospections),
            f"{execution_pct} %" if execution_pct is not None else "N/A",
            str(total_animation_lines), f"{total_animation_ca:,.0f}".replace(",", " "),
        ]]
        kpi_table = Table(kpi_data, colWidths=[48*mm, 48*mm, 42*mm, 38*mm, 48*mm])
        kpi_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#eaf3ed")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#24563a")),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTNAME", (0,1), (-1,1), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("GRID", (0,0), (-1,-1), .4, colors.HexColor("#d8e3db")),
            ("TOPPADDING", (0,0), (-1,-1), 7),
            ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ]))
        story.extend([kpi_table, Spacer(1, 6 * mm), Paragraph("Synthèse par collaborateur", styles["Heading2"])])
        summary_data = [[
            "Collaborateur", "Rôle", "Planning", "Prospections", "Hors planning",
            "Exécution", "Lignes animation", "CA animation (FCFA)", "Contrôle",
        ]]
        for row in summary_rows:
            is_vm = row["role"] == "Visiteur médical"
            is_animator = row["role"] == "Animateur(trice)"
            summary_data.append([
                row["name"], row["role"],
                str(row["planned"]) if is_vm else "-",
                str(row["prospections"]) if is_vm else "-",
                str(row["hors_planning"]) if is_vm else "-",
                f'{row["execution"]} %' if is_vm and row["execution"] is not None else "-",
                str(row["animation_lines"]) if is_animator else "-",
                f'{row["animation_ca"]:,.0f}'.replace(",", " ") if is_animator else "-",
                row["status_text"],
            ])
        summary_table = Table(summary_data, repeatRows=1, colWidths=[34*mm, 28*mm, 20*mm, 23*mm, 24*mm, 20*mm, 24*mm, 32*mm, 35*mm])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#eaf3ed")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#24563a")),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 7),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#d8e3db")),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f7faf8")]),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ]))
        story.extend([
            summary_table, Spacer(1, 6 * mm),
            Paragraph("Évolution quotidienne", styles["Heading2"]),
        ])
        daily_data = [[
            "Date", "Planifié", "Prospections", "Rattachées au planning",
            "Hors planning", "Lignes animation", "CA animation (FCFA)",
        ]]
        for row in daily_rows:
            daily_data.append([
                row["date"].strftime("%d/%m/%Y"), str(row["planned"]),
                str(row["prospections"]), str(row["planned_prospections"]),
                str(row["hors_planning"]), str(row["animation_lines"]),
                f'{row["animation_ca"]:,.0f}'.replace(",", " "),
            ])
        daily_table = Table(daily_data, repeatRows=1, colWidths=[30*mm, 25*mm, 30*mm, 38*mm, 30*mm, 32*mm, 40*mm])
        daily_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#eaf3ed")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#24563a")),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 7),
            ("ALIGN", (1,1), (-1,-1), "RIGHT"),
            ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#d8e3db")),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f7faf8")]),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ]))
        story.extend([
            daily_table, Spacer(1, 4 * mm),
            Paragraph(
                "Note : l’exécution compare les prospections rattachées au planning aux créneaux estimés. "
                "Les prospections hors planning sont présentées séparément. Un écart constitue un point à vérifier, "
                "pas une preuve d’absence d’activité. Les données proviennent des saisies enregistrées dans le CRM.",
                styles["NasoraSubtitle"],
            ),
        ])
        document.build(story)
        buffer.seek(0)
        return send_file(
            buffer,
            download_name=f"nasora_rapport_activite_{start_day.isoformat()}_{end_day.isoformat()}.pdf",
            as_attachment=True,
            mimetype="application/pdf",
        )
    if export_type == "collaborateurs":
        rows = []
        for row in summary_rows:
            is_vm = row["role"] == "Visiteur médical"
            is_animator = row["role"] == "Animateur(trice)"
            rows.append([
                row["name"], row["role"],
                row["planned"] if is_vm else "",
                row["prospections"] if is_vm else "",
                row["hors_planning"] if is_vm else "",
                row["execution"] if is_vm and row["execution"] is not None else "",
                row["animation_lines"] if is_animator else "",
                round(row["animation_ca"], 2) if is_animator else "",
                row["status_text"],
            ])
        filename = f"nasora_rapport_collaborateurs_{start_day.isoformat()}_{end_day.isoformat()}.csv"
        return _csv_response(filename, [
            "Collaborateur", "Rôle", "Créneaux planifiés", "Prospections",
            "Prospections hors planning", "Exécution (%)", "Lignes animation",
            "CA animation (FCFA)", "Contrôle",
        ], rows)
    if export_type == "quotidien":
        rows = [[
            row["date"].isoformat(), row["planned"], row["prospections"],
            row["planned_prospections"], row["hors_planning"],
            row["animation_lines"], round(row["animation_ca"], 2),
        ] for row in daily_rows]
        filename = f"nasora_rapport_quotidien_{start_day.isoformat()}_{end_day.isoformat()}.csv"
        return _csv_response(filename, [
            "Date", "Créneaux planifiés", "Prospections saisies",
            "Prospections rattachées au planning", "Prospections hors planning",
            "Lignes animation", "CA animation (FCFA)",
        ], rows)

    return render_template(
        "activity_reporting.html",
        start_day=start_day,
        end_day=end_day,
        division=division,
        divisions=list(DIVISION_SUPPLIERS.keys()),
        users=(
            User.query.filter(
                User.role.in_(("commercial", "animateur")),
                User.is_active_account.is_(True),
                User.project == division_filter,
            ).order_by(User.username).all()
            if division_filter
            else User.query.filter(
                User.role.in_(("commercial", "animateur")),
                User.is_active_account.is_(True),
            ).order_by(User.username).all()
        ),
        selected_commercial_id=selected_id,
        summary_rows=summary_rows,
        daily_rows=daily_rows,
        total_planned=total_planned,
        total_prospections=total_prospections,
        total_animation_lines=total_animation_lines,
        total_animation_ca=total_animation_ca,
        execution_pct=execution_pct,
    )
