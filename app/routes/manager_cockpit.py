from collections import Counter
from datetime import date, timedelta

from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models import AnimationSale, SalesObjective, SUPPLIERS, DIVISION_SUPPLIERS, User
from app.models_clients import Client, ClientVisit
from app.utils import roles_required
from app.visit_objectives_readonly import read_visit_targets

manager_cockpit_bp = Blueprint("manager_cockpit", __name__)


def _month_bounds(day):
    start = day.replace(day=1)
    end = day.replace(year=day.year + 1, month=1, day=1) if day.month == 12 else day.replace(month=day.month + 1, day=1)
    return start, end


def _revenue_for_range(division, start, end, commercial_id=None):
    total = 0.0
    product_counter = Counter()
    supplier_totals = {}
    for slug in DIVISION_SUPPLIERS.get(division, []):
        supplier = SUPPLIERS[slug]
        sale_model = supplier["sale_model"]
        product_model = supplier["product_model"]
        amount_expr = func.coalesce(sale_model.quantity, 0) * func.coalesce(sale_model.price, 0)
        query = db.session.query(product_model.name, func.coalesce(func.sum(sale_model.quantity), 0), func.coalesce(func.sum(amount_expr), 0)).join(sale_model, sale_model.product_id == product_model.id).filter(sale_model.project == division, sale_model.date >= start, sale_model.date < end)
        if commercial_id is not None:
            query = query.filter(sale_model.commercial_id == commercial_id)
        rows = query.group_by(product_model.id, product_model.name).all()
        supplier_total = 0.0
        for product_name, quantity, amount in rows:
            amount_value = float(amount or 0)
            supplier_total += amount_value
            product_counter[product_name] += int(quantity or 0)
        supplier_totals[supplier["label"]] = supplier_total
        total += supplier_total
    return total, product_counter, supplier_totals


def _animation_revenue(start, end, animateur_id=None):
    query = AnimationSale.query.filter(AnimationSale.animation_date >= start, AnimationSale.animation_date < end)
    if animateur_id is not None:
        query = query.filter(AnimationSale.animateur_id == animateur_id)
    rows = query.all()
    total = sum(float(row.total_amount or 0) for row in rows)
    quantities = Counter()
    pharmacies = Counter()
    for row in rows:
        quantities[row.product_name] += int(row.quantity or 0)
        pharmacies[row.pharmacy_name] += float(row.total_amount or 0)
    return total, len(rows), quantities, pharmacies


def _unique_visits(commercial_id=None, start=None, end=None):
    query = ClientVisit.query.filter(ClientVisit.is_duplicate.is_(False))
    if commercial_id is not None:
        query = query.filter(ClientVisit.commercial_id == commercial_id)
    if start is not None:
        query = query.filter(ClientVisit.date >= start)
    if end is not None:
        query = query.filter(ClientVisit.date < end)
    rows = query.order_by(ClientVisit.date.desc(), ClientVisit.id.desc()).all()
    seen = set()
    unique = []
    for row in rows:
        key = (row.commercial_id, row.client_id, row.date)
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def _ranking(commercials, division, start, end, visit_targets):
    ranking = []
    if not division:
        return ranking
    for commercial in commercials:
        revenue, _, _ = _revenue_for_range(division, start, end, commercial.id)
        visits = len(_unique_visits(commercial.id, start, end))
        target = int(visit_targets.get(commercial.id, 0) or 0)
        visit_pct = round(visits * 100 / target, 1) if target else 0.0
        ranking.append({"id": commercial.id, "name": commercial.username, "revenue": revenue, "visits": visits, "target": target, "visit_pct": visit_pct})
    ranking.sort(key=lambda row: (row["revenue"], row["visits"]), reverse=True)
    for index, row in enumerate(ranking, 1):
        row["rank"] = index
    return ranking


def _stock_alerts(division=None, limit=12):
    """Retourne les références actives en rupture ou stock très faible."""
    slugs = DIVISION_SUPPLIERS.keys() if not division else (division,)
    alerts = []
    stock_fields = ("stock_duopharm", "stock_ubipharm", "stock_laborex", "stock_sodipharm")
    labels = {"stock_duopharm": "Duopharm", "stock_ubipharm": "Ubipharm", "stock_laborex": "Laborex", "stock_sodipharm": "Sodipharm"}
    for item_division in slugs:
        for slug in DIVISION_SUPPLIERS.get(item_division, []):
            supplier = SUPPLIERS[slug]
            model = supplier["product_model"]
            products = model.query.filter_by(is_active=True).order_by(model.name).all()
            for product in products:
                for field in stock_fields:
                    quantity = int(getattr(product, field, 0) or 0)
                    if quantity <= 0:
                        alerts.append({"level": "danger", "product": product.name, "supplier": supplier["label"], "wholesaler": labels[field], "quantity": quantity, "text": "Rupture"})
                    elif quantity <= 5:
                        alerts.append({"level": "warning", "product": product.name, "supplier": supplier["label"], "wholesaler": labels[field], "quantity": quantity, "text": "Stock faible"})
    alerts.sort(key=lambda row: (row["quantity"] > 0, row["quantity"], row["product"]))
    return alerts[:limit]


@manager_cockpit_bp.route("/admin/cockpit-manager")
@login_required
@roles_required("admin")
def index():
    today = date.today()
    start, end = _month_bounds(today)
    previous_start = (start - timedelta(days=1)).replace(day=1)
    division = (request.args.get("division") or "").strip().lower()
    if division not in DIVISION_SUPPLIERS:
        division = "all"
    divisions = list(DIVISION_SUPPLIERS.keys())
    division_filter = None if division == "all" else division
    field_users = User.query.filter(User.role.in_(("commercial", "animateur")), User.is_active_account.is_(True)).order_by(User.username).all()
    animateurs = [user for user in field_users if user.role == "animateur"]
    selected_raw = (request.args.get("commercial_id") or "").strip()
    selected_commercial_id = int(selected_raw) if selected_raw.isdigit() else None
    if selected_commercial_id and not any(c.id == selected_commercial_id for c in field_users):
        selected_commercial_id = None

    if division_filter:
        revenue, product_counter, supplier_totals = _revenue_for_range(division_filter, start, end, selected_commercial_id)
        previous_revenue, _, _ = _revenue_for_range(division_filter, previous_start, start, selected_commercial_id)
        monthly_objective = SalesObjective.query.filter_by(division=division_filter, year=today.year, month=today.month).first()
    else:
        revenue = previous_revenue = 0.0
        product_counter = Counter()
        supplier_totals = {}
        for item_division in divisions:
            current_total, current_products, current_suppliers = _revenue_for_range(item_division, start, end, selected_commercial_id)
            previous_total, _, _ = _revenue_for_range(item_division, previous_start, start, selected_commercial_id)
            revenue += current_total
            previous_revenue += previous_total
            product_counter.update(current_products)
            for label, amount in current_suppliers.items():
                supplier_totals[label] = supplier_totals.get(label, 0.0) + amount
        monthly_objective = None

    visits = _unique_visits(selected_commercial_id, start, end)
    clients_query = Client.query.filter(Client.owner_id == selected_commercial_id) if selected_commercial_id else Client.query
    clients_count = clients_query.count()
    high_potential = clients_query.filter(Client.potential >= 4).count()
    animation_total, animation_lines, animation_products, animation_pharmacies = _animation_revenue(start, end)
    animation_animateurs = []
    for animateur in animateurs:
        amount, lines, _, _ = _animation_revenue(start, end, animateur.id)
        animation_animateurs.append({"name": animateur.username, "amount": amount, "lines": lines})
    animation_animateurs.sort(key=lambda row: row["amount"], reverse=True)

    visit_targets = read_visit_targets(field_users)
    ranking = _ranking(field_users, division_filter, start, end, visit_targets)
    if selected_commercial_id:
        ranking = [row for row in ranking if row["id"] == selected_commercial_id]
    objective_amount = float(monthly_objective.target_amount) if monthly_objective and monthly_objective.target_amount is not None else None
    revenue_pct = round(revenue * 100 / objective_amount, 1) if objective_amount else None
    previous_pct = round((revenue - previous_revenue) * 100 / previous_revenue, 1) if previous_revenue else None

    alerts = []
    overdue_query = Client.query.filter(Client.next_visit.isnot(None), Client.next_visit < today)
    if selected_commercial_id:
        overdue_query = overdue_query.filter(Client.owner_id == selected_commercial_id)
    overdue_count = overdue_query.count()
    if overdue_count:
        alerts.append({"level": "danger", "title": "Relances en retard", "text": f"{overdue_count} professionnel(s) ont une prochaine visite dépassée."})
    for row in ranking:
        if row["target"] and row["visit_pct"] < 50:
            alerts.append({"level": "warning", "title": "Activité terrain faible", "text": f"{row['name']} est à {row['visit_pct']} % de son objectif de visites."})
    if objective_amount and revenue_pct < 80:
        alerts.append({"level": "warning", "title": "CA sous l'objectif", "text": f"Le CA est à {revenue_pct} % de l'objectif mensuel."})
    if animation_total:
        alerts.append({"level": "success", "title": "Animations actives", "text": f"{animation_total:,.0f} FCFA générés par les animations ce mois."})
    stock_alerts = _stock_alerts(division_filter)
    for stock in stock_alerts[:5]:
        alerts.append({"level": stock["level"], "title": f"{stock['text']} stock", "text": f"{stock['product']} - {stock['supplier']} / {stock['wholesaler']} : {stock['quantity']} unité(s)."})

    return render_template(
        "manager_cockpit.html", today=today, start=start, end=end, divisions=divisions, division=division,
        commercials=field_users, selected_commercial_id=selected_commercial_id, revenue=revenue,
        previous_revenue=previous_revenue, previous_pct=previous_pct, objective_amount=objective_amount,
        revenue_pct=revenue_pct, visit_count=len(visits), clients_count=clients_count, high_potential=high_potential,
        animation_total=animation_total, animation_lines=animation_lines, supplier_totals=supplier_totals,
        ranking=ranking, alerts=alerts, stock_alerts=stock_alerts, top_products=product_counter.most_common(8),
        top_animation_products=animation_products.most_common(6),
        top_animation_pharmacies=sorted(animation_pharmacies.items(), key=lambda item: item[1], reverse=True)[:6],
        animation_animateurs=animation_animateurs,
    )
