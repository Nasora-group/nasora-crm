import logging
from calendar import monthrange
from collections import namedtuple
from datetime import date, datetime

from flask import Blueprint, render_template, flash, request, abort, jsonify, make_response
from flask_login import login_required, current_user
from sqlalchemy import func, text

from app.extensions import db
from app.models import User, Prospection, SUPPLIERS, DIVISION_SUPPLIERS, SalesObjective
from app.permissions import require_division
from app.utils import roles_required

logger = logging.getLogger(__name__)

revenue_bp = Blueprint("revenue", __name__)
ProductSaleRow = namedtuple("ProductSaleRow", ["name", "total_quantity", "total_revenue"])


def _division_suppliers(division):
    return [(slug, SUPPLIERS[slug]["label"], SUPPLIERS[slug]["sale_model"], SUPPLIERS[slug]["product_model"]) for slug in DIVISION_SUPPLIERS.get(division, [])]


def _ensure_division_access(division):
    require_division(division)


def _commercial_only_scope():
    """True when the current user must only see their own commercial data."""
    return getattr(current_user, "role", None) == "commercial"


def _month_expression(sale_model):
    """Expression mensuelle compatible PostgreSQL et SQLite (utilisé par la CI)."""
    if db.engine.dialect.name == "sqlite":
        return func.strftime("%Y-%m", sale_model.date)
    return func.to_char(sale_model.date, "YYYY-MM")


def _monthly_revenue_for_division(division):
    """Retourne le CA mensuel directement depuis les tables de ventes.

    Cette lecture SQL volontairement simple évite qu'une relation ORM ou une
    différence de mapping entre environnements empêche la remontée du CA.
    Aucune écriture n'est effectuée.
    """
    combined = {}
    for slug, _label, sale_model, _product_model in _division_suppliers(division):
        table_name = sale_model.__tablename__
        conditions = ["project = :division"]
        params = {"division": division}
        if _commercial_only_scope():
            conditions.append("commercial_id = :commercial_id")
            params["commercial_id"] = current_user.id
        sql = text(
            f"SELECT TO_CHAR(date, 'YYYY-MM') AS month, "
            f"COALESCE(SUM(COALESCE(quantity, 0) * COALESCE(price, 0)), 0) AS revenue "
            f"FROM {table_name} WHERE {' AND '.join(conditions)} "
            f"GROUP BY TO_CHAR(date, 'YYYY-MM') ORDER BY TO_CHAR(date, 'YYYY-MM')"
        )
        rows = db.session.execute(sql, params).mappings().all()
        for row in rows:
            month = row["month"]
            combined.setdefault(month, {})[slug] = float(row["revenue"] or 0)

    labels = sorted(combined.keys())
    totals = [sum(combined[month].values()) for month in labels]
    logger.info("CA mensuel %s chargé: %s mois, %.2f EUR", division, len(labels), sum(totals))
    return labels, totals, combined


def _objectives_kpis(division, labels, totals):
    today = date.today(); current_month_key = today.strftime("%Y-%m"); current_year = today.year
    total_revenue = sum(float(amount or 0) for amount in totals)
    monthly_avg = total_revenue / len(labels) if labels else 0.0
    current_month_revenue = next((float(amount or 0) for month, amount in zip(labels, totals) if month == current_month_key), 0.0)
    current_year_revenue = sum(float(amount or 0) for month, amount in zip(labels, totals) if month.startswith(str(current_year)))
    monthly_target = annual_target = None; objectives_available = True
    try:
        monthly_objective = SalesObjective.query.filter_by(division=division, year=current_year, month=today.month).first()
        annual_objective = SalesObjective.query.filter_by(division=division, year=current_year, month=None).first()
        monthly_target = float(monthly_objective.target_amount) if monthly_objective and monthly_objective.target_amount is not None else None
        annual_target = float(annual_objective.target_amount) if annual_objective and annual_objective.target_amount is not None else None
    except Exception:
        db.session.rollback(); logger.warning("Impossible de lire les objectifs (%s)", division, exc_info=True); objectives_available = False
    return {"monthly_avg": monthly_avg, "current_month_revenue": current_month_revenue, "current_year_revenue": current_year_revenue, "monthly_target": monthly_target, "annual_target": annual_target, "monthly_pct": current_month_revenue / monthly_target * 100.0 if monthly_target else None, "annual_pct": current_year_revenue / annual_target * 100.0 if annual_target else None, "current_year": current_year, "current_month_label": current_month_key, "objectives_available": objectives_available}


def _division_visit_ranking(division, limit=5):
    query = db.session.query(User.username, User.zone, func.count(Prospection.id).label("nombre_visites")).join(Prospection, Prospection.commercial_id == User.id).filter(User.project == division, User.role == "commercial")
    if _commercial_only_scope():
        query = query.filter(User.id == current_user.id)
    return query.group_by(User.id, User.username, User.zone).order_by(func.count(Prospection.id).desc(), User.username.asc()).limit(limit).all()


def _division_dashboard(division, template_name):
    _ensure_division_access(division)
    prospection_query = Prospection.query.join(User).filter(User.project == division)
    if _commercial_only_scope():
        prospection_query = prospection_query.filter(Prospection.commercial_id == current_user.id)
    prospections = prospection_query.order_by(Prospection.date.desc()).all()
    labels, totals, _ = _monthly_revenue_for_division(division); objectives_kpis = _objectives_kpis(division, labels, totals); top_5_commerciaux = _division_visit_ranking(division)
    commerciaux_query = User.query.filter_by(project=division, role="commercial")
    if _commercial_only_scope():
        commerciaux_query = commerciaux_query.filter(User.id == current_user.id)
    commerciaux = commerciaux_query.order_by(User.username).all(); suppliers = _division_suppliers(division)
    return render_template(template_name, monthly_revenue_labels=labels, monthly_revenue_data=totals, top_5_commerciaux=top_5_commerciaux, commerciaux=commerciaux, prospections=prospections, suppliers=suppliers, division=division, kpis=objectives_kpis)


@revenue_bp.route("/nasderm_dashboard")
@login_required
@roles_required("admin", "commercial")
def nasderm_dashboard():
    return _division_dashboard("nasderm", "nasderm_dashboard.html")


@revenue_bp.route("/nasmedic_dashboard")
@login_required
@roles_required("admin", "commercial")
def nasmedic_dashboard():
    return _division_dashboard("nasmedic", "nasmedic_dashboard.html")


def _monthly_revenue_route(division, template_name):
    _ensure_division_access(division)
    suppliers = _division_suppliers(division)
    labels, totals, combined = _monthly_revenue_for_division(division)
    rows = [
        {
            "month": month,
            "amounts": {slug: combined[month].get(slug, 0.0) for slug, *_ in suppliers},
            "total": sum(combined[month].get(slug, 0.0) for slug, *_ in suppliers),
        }
        for month in labels
    ]
    response = make_response(render_template(
        template_name,
        rows=rows,
        suppliers=suppliers,
        kpis=_objectives_kpis(division, labels, totals),
        division=division,
        monthly_revenue_labels=labels,
    ))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@revenue_bp.route("/monthly_revenue_nasderm")
@login_required
@roles_required("admin", "commercial")
def monthly_revenue_nasderm():
    return _monthly_revenue_route("nasderm", "monthly_revenue_nasderm.html")


@revenue_bp.route("/monthly_revenue_nasmedic")
@login_required
@roles_required("admin", "commercial")
def monthly_revenue_nasmedic():
    return _monthly_revenue_route("nasmedic", "monthly_revenue_nasmedic.html")


@revenue_bp.route("/admin_dashboard_chart_data")
@login_required
@roles_required("admin")
def admin_dashboard_chart_data():
    """Données JSON dédiées aux graphiques du tableau de bord Direction."""
    try:
        labels_nasmedic, totals_nasmedic, _ = _monthly_revenue_for_division("nasmedic")
        labels_nasderm, totals_nasderm, _ = _monthly_revenue_for_division("nasderm")
        all_labels = sorted(set(labels_nasmedic) | set(labels_nasderm))
        nasmedic_by_month = dict(zip(labels_nasmedic, totals_nasmedic))
        nasderm_by_month = dict(zip(labels_nasderm, totals_nasderm))
        return jsonify({
            "labels": all_labels,
            "totals": [nasmedic_by_month.get(m, 0.0) + nasderm_by_month.get(m, 0.0) for m in all_labels],
            "divisions": {
                "nasmedic": sum(totals_nasmedic),
                "nasderm": sum(totals_nasderm),
            },
        })
    except Exception:
        db.session.rollback()
        logger.exception("Impossible de charger les données des graphiques Direction")
        return jsonify({"labels": [], "totals": [], "divisions": {"nasmedic": 0, "nasderm": 0}}), 500


def _month_bounds(month):
    try: parsed = datetime.strptime(month, "%Y-%m")
    except ValueError: abort(404)
    start = date(parsed.year, parsed.month, 1); end = date(parsed.year + 1, 1, 1) if parsed.month == 12 else date(parsed.year, parsed.month + 1, 1)
    return start, end


def _product_sales_detail(sale_model, product_model, month, division):
    start, end = _month_bounds(month); amount_expr = func.coalesce(sale_model.quantity, 0) * func.coalesce(sale_model.price, 0)
    query = db.session.query(product_model.name, func.coalesce(func.sum(sale_model.quantity), 0).label("total_quantity"), func.coalesce(func.sum(amount_expr), 0).label("total_revenue")).join(sale_model, sale_model.product_id == product_model.id).filter(sale_model.project == division, sale_model.date >= start, sale_model.date < end)
    if _commercial_only_scope():
        query = query.filter(sale_model.commercial_id == current_user.id)
    rows = query.group_by(product_model.id, product_model.name).order_by(product_model.name.asc()).all()
    return [ProductSaleRow(name=name, total_quantity=quantity, total_revenue=float(revenue or 0)) for name, quantity, revenue in rows]


def _monthly_revenue_detail_route(division, month, template_name):
    _ensure_division_access(division); suppliers = _division_suppliers(division); details = {slug: _product_sales_detail(sale_model, product_model, month, division) for slug, _label, sale_model, product_model in suppliers}
    return render_template(template_name, month=month, suppliers=suppliers, details=details)


@revenue_bp.route("/monthly_revenue_detail_nasderm/<month>")
@login_required
@roles_required("admin", "commercial")
def monthly_revenue_detail_nasderm(month):
    return _monthly_revenue_detail_route("nasderm", month, "monthly_revenue_detail_nasderm.html")


@revenue_bp.route("/monthly_revenue_detail_nasmedic/<month>")
@login_required
@roles_required("admin", "commercial")
def monthly_revenue_detail_nasmedic(month):
    return _monthly_revenue_detail_route("nasmedic", month, "monthly_revenue_detail_nasmedic.html")
