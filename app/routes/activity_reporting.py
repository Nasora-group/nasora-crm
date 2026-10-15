from collections import Counter, defaultdict
from datetime import date, timedelta

from flask import Blueprint, render_template, request
from flask_login import login_required

from app.models import AnimationSale, DIVISION_SUPPLIERS, Planning, Prospection, User
from app.utils import decode_planning_slot, roles_required

activity_reporting_bp = Blueprint("activity_reporting", __name__)


def _parse_day(value, fallback):
    try:
        return date.fromisoformat(value) if value else fallback
    except (TypeError, ValueError):
        return fallback


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

    users = User.query.filter(
        User.role.in_(("commercial", "animateur")),
        User.is_active_account.is_(True),
    ).order_by(User.username).all()
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
                    slots = len(decode_planning_slot(getattr(plan, field, None)))
                    planned_by_user[plan.commercial_id] += slots
                    planned_by_day[planned_date] += slots

    prospection_by_user = Counter()
    prospection_by_day = Counter()
    if user_ids:
        prospections = Prospection.query.filter(
            Prospection.commercial_id.in_(user_ids),
            Prospection.date >= start_day,
            Prospection.date < end_exclusive,
        ).all()
        for row in prospections:
            prospection_by_user[row.commercial_id] += 1
            prospection_by_day[row.date] += 1

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
        animation_lines = animation_lines_by_user[user.id] if user.role == "animateur" else 0
        animation_ca = animation_ca_by_user[user.id] if user.role == "animateur" else 0.0
        execution = round(prospect_count * 100 / planned, 1) if planned else None
        if user.role == "commercial":
            status = "warning" if planned and prospect_count < planned else ("success" if prospect_count else "neutral")
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
            "animation_lines": animation_lines_by_day[day],
            "animation_ca": animation_ca_by_day[day],
        })
        day += timedelta(days=1)

    total_planned = sum(row["planned"] for row in summary_rows)
    total_prospections = sum(row["prospections"] for row in summary_rows)
    total_animation_lines = sum(row["animation_lines"] for row in summary_rows)
    total_animation_ca = sum(row["animation_ca"] for row in summary_rows)
    execution_pct = round(total_prospections * 100 / total_planned, 1) if total_planned else None

    return render_template(
        "activity_reporting.html",
        start_day=start_day,
        end_day=end_day,
        division=division,
        divisions=list(DIVISION_SUPPLIERS.keys()),
        users=User.query.filter(
            User.role.in_(("commercial", "animateur")),
            User.is_active_account.is_(True),
        ).order_by(User.username).all(),
        selected_commercial_id=selected_id,
        summary_rows=summary_rows,
        daily_rows=daily_rows,
        total_planned=total_planned,
        total_prospections=total_prospections,
        total_animation_lines=total_animation_lines,
        total_animation_ca=total_animation_ca,
        execution_pct=execution_pct,
    )
