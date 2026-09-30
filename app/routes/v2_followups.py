from datetime import date, timedelta

from flask import Blueprint, render_template, request
from flask_login import login_required

from app.models import User, DIVISION_SUPPLIERS
from app.models_clients import Client
from app.utils import roles_required

v2_followups_bp = Blueprint("v2_followups", __name__, url_prefix="/v2/relances")


@v2_followups_bp.route("")
@login_required
@roles_required("admin")
def index():
    today = date.today()
    division = (request.args.get("division") or "all").lower()
    user_id = request.args.get("user_id", type=int)
    horizon = request.args.get("horizon", 30, type=int)
    if horizon not in (7, 30, 60):
        horizon = 30

    divisions = list(DIVISION_SUPPLIERS)
    selected_divisions = divisions if division == "all" else [division] if division in divisions else divisions

    users = (
        User.query.filter(
            User.role.in_(["commercial", "animateur"]),
            User.project.in_(selected_divisions),
            User.is_active_account.is_(True),
        )
        .order_by(User.project, User.username)
        .all()
    )
    selected_user_id = user_id if user_id and any(user.id == user_id for user in users) else None

    query = (
        Client.query
        .join(User, Client.owner_id == User.id)
        .filter(
            Client.next_visit.isnot(None),
            User.role.in_(["commercial", "animateur"]),
            User.is_active_account.is_(True),
            User.project.in_(selected_divisions),
        )
    )
    if selected_user_id:
        query = query.filter(Client.owner_id == selected_user_id)

    end_date = today + timedelta(days=horizon)
    rows = query.filter(Client.next_visit <= end_date).order_by(Client.next_visit.asc(), Client.name.asc()).all()

    overdue = [row for row in rows if row.next_visit < today]
    due_today = [row for row in rows if row.next_visit == today]
    upcoming = [row for row in rows if today < row.next_visit <= end_date]

    return render_template(
        "v2/followups.html",
        rows=rows,
        overdue=overdue,
        due_today=due_today,
        upcoming=upcoming,
        today=today,
        end_date=end_date,
        horizon=horizon,
        division=division if division in divisions or division == "all" else "all",
        divisions=divisions,
        users=users,
        selected_user_id=selected_user_id,
    )
