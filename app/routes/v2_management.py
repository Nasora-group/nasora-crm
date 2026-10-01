from datetime import date, timedelta

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models import User, Prospection, Planning, AnimationSale
from app.models_clients import ClientVisit
from app.models_v2_complete import V2PlanningExecution
from app.permissions import can_manage_field_team, management_scope

management_bp = Blueprint("v2_management", __name__, url_prefix="/v2")


def _scope_users():
    scope = management_scope()
    query = User.query.filter(
        User.role.in_(("commercial", "animateur")),
        User.is_active_account.is_(True),
    )
    if scope["level"] == "division":
        query = query.filter(User.project == scope["division"])
    elif scope["level"] == "zone":
        query = query.filter(User.project == scope["division"], User.zone == scope["zone"])
    return query.order_by(User.project, User.zone, User.username).all()


@management_bp.route("/management")
@login_required
def management():
    if not can_manage_field_team():
        return ("Forbidden", 403)

    today = date.today()
    start = date(today.year, today.month, 1)
    end = date(today.year + 1, 1, 1) if today.month == 12 else date(today.year, today.month + 1, 1)
    users = _scope_users()
    user_ids = [u.id for u in users]

    prospections = Prospection.query.filter(
        Prospection.date >= start, Prospection.date < end,
        Prospection.commercial_id.in_(user_ids) if user_ids else False,
    ).count()

    visits = ClientVisit.query.filter(
        ClientVisit.date >= start, ClientVisit.date < end,
        ClientVisit.is_duplicate.is_(False),
        ClientVisit.commercial_id.in_(user_ids) if user_ids else False,
    ).count()

    planned = V2PlanningExecution.query.filter(
        V2PlanningExecution.execution_date >= start,
        V2PlanningExecution.execution_date < end,
        V2PlanningExecution.user_id.in_(user_ids) if user_ids else False,
    ).count()
    realized = V2PlanningExecution.query.filter(
        V2PlanningExecution.execution_date >= start,
        V2PlanningExecution.execution_date < end,
        V2PlanningExecution.user_id.in_(user_ids) if user_ids else False,
        V2PlanningExecution.status == "realized",
    ).count()

    animation_lines = AnimationSale.query.filter(
        AnimationSale.animation_date >= start, AnimationSale.animation_date < end,
        AnimationSale.animateur_id.in_(user_ids) if user_ids else False,
    ).count()

    rows = []
    for user in users:
        user_prospections = Prospection.query.filter(
            Prospection.commercial_id == user.id,
            Prospection.date >= start, Prospection.date < end,
        ).count()
        user_visits = ClientVisit.query.filter(
            ClientVisit.commercial_id == user.id,
            ClientVisit.date >= start, ClientVisit.date < end,
            ClientVisit.is_duplicate.is_(False),
        ).count()
        user_planned = V2PlanningExecution.query.filter(
            V2PlanningExecution.user_id == user.id,
            V2PlanningExecution.execution_date >= start,
            V2PlanningExecution.execution_date < end,
        ).count()
        user_realized = V2PlanningExecution.query.filter(
            V2PlanningExecution.user_id == user.id,
            V2PlanningExecution.execution_date >= start,
            V2PlanningExecution.execution_date < end,
            V2PlanningExecution.status == "realized",
        ).count()
        rows.append({
            "user": user,
            "prospections": user_prospections,
            "visits": user_visits,
            "planned": user_planned,
            "realized": user_realized,
            "execution_rate": round(user_realized * 100 / user_planned, 1) if user_planned else 0,
        })

    return render_template(
        "v2/management.html",
        scope=management_scope(),
        month=today.strftime("%m/%Y"),
        users=rows,
        kpis={
            "team": len(users),
            "prospections": prospections,
            "visits": visits,
            "planned": planned,
            "realized": realized,
            "execution_rate": round(realized * 100 / planned, 1) if planned else 0,
            "animations": animation_lines,
        },
    )
