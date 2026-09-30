from datetime import date
from decimal import Decimal

from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models import User, SalesObjective, DIVISION_SUPPLIERS, SUPPLIERS, Prospection, AnimationSale
from app.models_clients import ClientVisit
from app.utils import roles_required

v2_performance_bp = Blueprint("v2_performance", __name__, url_prefix="/v2/performance")

MONTHS = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
    7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre",
}


def _period(year, month):
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


def _revenue(division, start, end):
    total = Decimal("0")
    for slug in DIVISION_SUPPLIERS.get(division, []):
        model = SUPPLIERS[slug]["sale_model"]
        total += Decimal(str(
            db.session.query(
                func.coalesce(func.sum(model.quantity * model.price), 0)
            ).filter(
                model.date >= start,
                model.date < end,
                model.project == division,
            ).scalar() or 0
        ))
    return total


def _aggregate_team(users, divisions, start, end):
    user_ids = [user.id for user in users]
    if not user_ids:
        return []

    user_divisions = {user.id: user.project for user in users}

    prospections = dict(
        db.session.query(
            Prospection.commercial_id,
            func.count(Prospection.id),
        ).filter(
            Prospection.commercial_id.in_(user_ids),
            Prospection.date >= start,
            Prospection.date < end,
        ).group_by(Prospection.commercial_id).all()
    )

    visits = dict(
        db.session.query(
            ClientVisit.commercial_id,
            func.count(ClientVisit.id),
        ).filter(
            ClientVisit.commercial_id.in_(user_ids),
            ClientVisit.date >= start,
            ClientVisit.date < end,
            ClientVisit.is_duplicate.is_(False),
        ).group_by(ClientVisit.commercial_id).all()
    )

    animation_rows = (
        db.session.query(
            AnimationSale.animateur_id,
            func.count(AnimationSale.id),
            func.coalesce(func.sum(AnimationSale.total_amount), 0),
        ).filter(
            AnimationSale.animateur_id.in_(user_ids),
            AnimationSale.animation_date >= start,
            AnimationSale.animation_date < end,
            AnimationSale.project.in_(divisions),
        ).group_by(AnimationSale.animateur_id).all()
    )
    animations = {
        row[0]: (int(row[1] or 0), Decimal(str(row[2] or 0)))
        for row in animation_rows
    }

    sales_by_user = {user.id: Decimal("0") for user in users}
    for division in divisions:
        division_user_ids = [user.id for user in users if user_divisions[user.id] == division]
        if not division_user_ids:
            continue
        for slug in DIVISION_SUPPLIERS.get(division, []):
            model = SUPPLIERS[slug]["sale_model"]
            rows = db.session.query(
                model.commercial_id,
                func.coalesce(func.sum(model.quantity * model.price), 0),
            ).filter(
                model.commercial_id.in_(division_user_ids),
                model.date >= start,
                model.date < end,
                model.project == division,
            ).group_by(model.commercial_id).all()
            for user_id, amount in rows:
                sales_by_user[user_id] += Decimal(str(amount or 0))

    team = []
    for user in users:
        animation_lines, animation_ca = animations.get(user.id, (0, Decimal("0")))
        sales_ca = sales_by_user[user.id]
        team.append({
            "user": user,
            "prospections": int(prospections.get(user.id, 0)),
            "visits": int(visits.get(user.id, 0)),
            "animation_lines": animation_lines,
            "animation_ca": animation_ca,
            "sales_ca": sales_ca,
            "total_ca": sales_ca + animation_ca,
        })
    return team


@v2_performance_bp.route("")
@login_required
@roles_required("admin")
def index():
    today = date.today()
    year = request.args.get("year", today.year, type=int)
    month = request.args.get("month", today.month, type=int)
    if month < 1 or month > 12:
        month = today.month

    division = (request.args.get("division") or "all").lower()
    start, end = _period(year, month)
    divisions = (
        list(DIVISION_SUPPLIERS)
        if division == "all"
        else [division]
        if division in DIVISION_SUPPLIERS
        else list(DIVISION_SUPPLIERS)
    )

    targets = {
        row.division: Decimal(str(row.target_amount or 0))
        for row in SalesObjective.query.filter(
            SalesObjective.division.in_(divisions),
            SalesObjective.year == year,
            SalesObjective.month == month,
        ).all()
    }
    division_rows = []
    for div in divisions:
        target_amount = targets.get(div, Decimal("0"))
        ca = _revenue(div, start, end)
        rate = (ca / target_amount * 100) if target_amount else None
        division_rows.append({
            "division": div,
            "target": target_amount,
            "ca": ca,
            "rate": rate,
        })

    users = (
        User.query.filter(
            User.role.in_(["commercial", "animateur"]),
            User.project.in_(divisions),
            User.is_active_account.is_(True),
        )
        .order_by(User.project, User.username)
        .all()
    )
    team = _aggregate_team(users, divisions, start, end)

    total_target = sum((x["target"] for x in division_rows), Decimal("0"))
    total_ca = sum((x["ca"] for x in division_rows), Decimal("0"))
    total_animation_ca = sum((x["animation_ca"] for x in team), Decimal("0"))

    return render_template(
        "v2/performance.html",
        year=year,
        month=month,
        month_label=MONTHS[month],
        division=division,
        division_rows=division_rows,
        team=team,
        total_target=total_target,
        total_ca=total_ca,
        total_animation_ca=total_animation_ca,
        total_rate=(total_ca / total_target * 100 if total_target else None),
    )


@v2_performance_bp.route("/objectifs")
@login_required
@roles_required("admin")
def objectives():
    year = request.args.get("year", date.today().year, type=int)
    objectives = SalesObjective.query.filter_by(year=year).all()
    grouped = {}
    for row in objectives:
        grouped[(row.division, row.month)] = row.target_amount

    rows = []
    for div in DIVISION_SUPPLIERS:
        rows.append({
            "division": div,
            "annual": grouped.get((div, None), 0),
            "months": [grouped.get((div, month), 0) for month in range(1, 13)],
        })
    return render_template(
        "v2/performance_objectives.html",
        year=year,
        rows=rows,
        months=MONTHS,
    )
