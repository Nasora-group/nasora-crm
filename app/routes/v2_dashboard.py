from collections import Counter
from datetime import date, timedelta

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models import (
    AnimationSale,
    DIVISION_SUPPLIERS,
    Planning,
    Prospection,
    SUPPLIERS,
    User,
)
from app.models_clients import Client, ClientVisit
from app.models_stock import StockEntry
from app.permissions import is_admin
from app.utils import decode_planning_slot, roles_required

v2_dashboard_bp = Blueprint("v2_dashboard", __name__, url_prefix="/v2")


def _parse_date(value, fallback):
    try:
        return date.fromisoformat(value) if value else fallback
    except ValueError:
        return fallback


def _scope_users(division):
    query = User.query.filter(User.role.in_(["commercial", "animateur"]))
    if division in DIVISION_SUPPLIERS:
        query = query.filter(User.project == division)
    return query.order_by(User.username.asc()).all()


def _selected_users(division, user_id):
    users = _scope_users(division)
    if user_id:
        users = [user for user in users if user.id == user_id]
    return users


def _revenue_kpi(division, start, end, user_id=None):
    total = 0.0
    by_supplier = {}
    supplier_defs = DIVISION_SUPPLIERS.get(division, [])
    for slug in supplier_defs:
        supplier = SUPPLIERS[slug]
        sale_model = supplier["sale_model"]
        query = db.session.query(
            func.coalesce(
                func.sum(
                    func.coalesce(sale_model.quantity, 0)
                    * func.coalesce(sale_model.price, 0)
                ),
                0,
            )
        ).filter(
            sale_model.project == division,
            sale_model.date >= start,
            sale_model.date < end,
        )
        if user_id:
            query = query.filter(sale_model.commercial_id == user_id)
        amount = float(query.scalar() or 0)
        by_supplier[slug] = {
            "label": supplier["label"],
            "amount": amount,
        }
        total += amount
    return total, by_supplier


def _planning_kpi(start, end, user_id=None):
    query = Planning.query.filter(Planning.date >= start, Planning.date < end)
    if user_id:
        query = query.filter(Planning.commercial_id == user_id)
    rows = query.all()
    slots = 0
    structures = 0
    for planning in rows:
        for field in ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"):
            entries = decode_planning_slot(getattr(planning, field, None))
            slots += len(entries)
            structures += sum(1 for _type, name in entries if name.strip())
    return len(rows), slots, structures


def _animation_kpi(division, start, end, user_id=None):
    query = AnimationSale.query.filter(
        AnimationSale.project == division,
        AnimationSale.animation_date >= start,
        AnimationSale.animation_date < end,
    )
    if user_id:
        query = query.filter(AnimationSale.animateur_id == user_id)
    rows = query.all()
    return {
        "sales_lines": len(rows),
        "quantity": sum(row.quantity for row in rows),
        "revenue": sum(float(row.total_amount) for row in rows),
        "pharmacies": len({row.pharmacy_name.strip().lower() for row in rows if row.pharmacy_name}),
    }


def _stock_kpi(division):
    if division not in DIVISION_SUPPLIERS:
        return {"ruptures": 0, "faible": 0}
    current_monday = date.today() - timedelta(days=date.today().weekday())
    query = StockEntry.query.filter_by(week_start=current_monday, division=division)
    rows = query.all()
    return {
        "ruptures": sum(1 for row in rows if row.quantity <= 0),
        "faible": sum(1 for row in rows if 0 < row.quantity <= 10),
    }


@v2_dashboard_bp.route("/pilotage", methods=["GET"])
@login_required
@roles_required("admin")
def pilotage():
    today = date.today()
    default_start = today.replace(day=1)
    start = _parse_date(request.args.get("date_start"), default_start)
    end = _parse_date(request.args.get("date_end"), today + timedelta(days=1))
    if end <= start:
        end = start + timedelta(days=1)

    division = (request.args.get("division") or "all").strip().lower()
    if division not in {"all", *DIVISION_SUPPLIERS.keys()}:
        division = "all"

    raw_user_id = (request.args.get("user_id") or "").strip()
    selected_user_id = int(raw_user_id) if raw_user_id.isdigit() else None
    if selected_user_id:
        selected_user = db.session.get(User, selected_user_id)
        if not selected_user or selected_user.role not in {"commercial", "animateur"}:
            selected_user_id = None

    divisions = list(DIVISION_SUPPLIERS.keys()) if division == "all" else [division]
    users = _scope_users(division if division != "all" else None)
    if selected_user_id:
        users = [user for user in users if user.id == selected_user_id]

    prospection_query = Prospection.query.filter(
        Prospection.date >= start,
        Prospection.date < end,
    ).join(User, Prospection.commercial_id == User.id).filter(
        User.role == "commercial",
    )
    if division != "all":
        prospection_query = prospection_query.filter(User.project == division)
    if selected_user_id:
        prospection_query = prospection_query.filter(Prospection.commercial_id == selected_user_id)
    prospections = prospection_query.all()

    professionals = {
        f"{row.telephone.strip() if row.telephone else ''}|"
        f"{(row.nom_client or '').strip().lower()}|"
        f"{(row.establishment or row.structure or '').strip().lower()}"
        for row in prospections
    }
    professionals.discard("||")

    visit_query = ClientVisit.query.filter(
        ClientVisit.date >= start,
        ClientVisit.date < end,
        ClientVisit.is_duplicate.is_(False),
    ).join(User, ClientVisit.commercial_id == User.id).filter(
        User.role == "commercial",
    )
    if division != "all":
        visit_query = visit_query.filter(User.project == division)
    if selected_user_id:
        visit_query = visit_query.filter(ClientVisit.commercial_id == selected_user_id)
    real_visits = visit_query.count()

    planning_weeks, planned_slots, named_structures = _planning_kpi(start, end, selected_user_id)

    revenue = 0.0
    revenue_by_division = {}
    animation = {"sales_lines": 0, "quantity": 0, "revenue": 0.0, "pharmacies": 0}
    stock = {"ruptures": 0, "faible": 0}
    for current_division in divisions:
        amount, supplier_rows = _revenue_kpi(current_division, start, end, selected_user_id)
        revenue += amount
        revenue_by_division[current_division] = {
            "amount": amount,
            "suppliers": supplier_rows,
        }
        current_animation = _animation_kpi(current_division, start, end, selected_user_id)
        animation["sales_lines"] += current_animation["sales_lines"]
        animation["quantity"] += current_animation["quantity"]
        animation["revenue"] += current_animation["revenue"]
        animation["pharmacies"] += current_animation["pharmacies"]
        current_stock = _stock_kpi(current_division)
        stock["ruptures"] += current_stock["ruptures"]
        stock["faible"] += current_stock["faible"]

    upcoming_query = Client.query.filter(
        Client.next_visit.isnot(None),
        Client.next_visit >= today,
        Client.next_visit <= today + timedelta(days=7),
    )
    if division != "all":
        upcoming_query = upcoming_query.join(User, Client.owner_id == User.id).filter(User.project == division)
    if selected_user_id:
        upcoming_query = upcoming_query.filter(Client.owner_id == selected_user_id)
    upcoming_followups = upcoming_query.count()

    performance = []
    for user in users:
        user_prospections = sum(1 for row in prospections if row.commercial_id == user.id)
        user_visits = sum(1 for row in real_visits and [] )
        performance.append({
            "user": user,
            "prospections": user_prospections,
            "visits": user_visits,
        })

    kpis = {
        "revenue": revenue,
        "prospections": len(prospections),
        "professionals": len(professionals),
        "real_visits": real_visits,
        "planning_weeks": planning_weeks,
        "planned_slots": planned_slots,
        "named_structures": named_structures,
        "animation": animation,
        "stock": stock,
        "upcoming_followups": upcoming_followups,
    }

    return render_template(
        "v2/pilotage.html",
        kpis=kpis,
        revenue_by_division=revenue_by_division,
        performance=performance,
        users=users,
        divisions=DIVISION_SUPPLIERS.keys(),
        selected_division=division,
        selected_user_id=selected_user_id,
        date_start=start.isoformat(),
        date_end=(end - timedelta(days=1)).isoformat(),
        today=today,
        is_admin=is_admin(),
    )
