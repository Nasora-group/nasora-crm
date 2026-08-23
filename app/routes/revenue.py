import logging
from calendar import monthrange
from collections import namedtuple
from datetime import date, datetime

from flask import Blueprint, render_template, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db
from app.models import User, Prospection, SUPPLIERS, DIVISION_SUPPLIERS, SalesObjective
from app.utils import roles_required

logger = logging.getLogger(__name__)

revenue_bp = Blueprint("revenue", __name__)

ProductSaleRow = namedtuple("ProductSaleRow", ["name", "total_quantity", "total_revenue"])


def _division_suppliers(division):
    return [
        (slug, SUPPLIERS[slug]["label"], SUPPLIERS[slug]["sale_model"], SUPPLIERS[slug]["product_model"])
        for slug in DIVISION_SUPPLIERS.get(division, [])
    ]


def _ensure_division_access(division):
    """Les commerciaux ne peuvent consulter que leur propre division."""
    if current_user.role == "commercial" and current_user.project != division:
        abort(403)


def _monthly_revenue_for_division(division):
    """Agrège le CA mensuel côté PostgreSQL au lieu de charger toutes les ventes."""
    combined = {}
    for slug, _label, sale_model, _product_model in _division_suppliers(division):
        month_expr = func.to_char(sale_model.date, "YYYY-MM")
        amount_expr = func.coalesce(sale_model.quantity, 0) * func.coalesce(sale_model.price, 0)
        rows = (
            db.session.query(
                month_expr.label("month"),
                func.coalesce(func.sum(amount_expr), 0).label("revenue"),
            )
            .filter(sale_model.project == division)
            .group_by(month_expr)
            .order_by(month_expr)
            .all()
        )
        for month, revenue in rows:
            combined.setdefault(month, {})[slug] = float(revenue or 0)

    labels = sorted(combined.keys())
    totals = [sum(combined[m].values()) for m in labels]
    return labels, totals, combined


def _objectives_kpis(division, labels, totals):
    today = date.today()
    current_month_key = today.strftime("%Y-%m")
    current_year = today.year
    total_revenue = sum(float(amount or 0) for amount in totals)
    monthly_avg = (total_revenue / len(labels)) if labels else 0.0
    current_month_revenue = next((float(amount or 0) for month, amount in zip(labels, totals) if month == current_month_key), 0.0)
    current_year_revenue = sum(float(amount or 0) for month, amount in zip(labels, totals) if month.startswith(str(current_year)))

    monthly_target = None
    annual_target = None
    objectives_available = True
    try:
        monthly_objective = SalesObjective.query.filter_by(division=division, year=current_year, month=today.month).first()
        annual_objective = SalesObjective.query.filter_by(division=division, year=current_year, month=None).first()
        monthly_target = float(monthly_objective.target_amount) if monthly_objective and monthly_objective.target_amount is not None else None
        annual_target = float(annual_objective.target_amount) if annual_objective and annual_objective.target_amount is not None else None
    except Exception:
        db.session.rollback()
        logger.warning("Impossible de lire les objectifs (%s)", division, exc_info=True)
        objectives_available = False

    return {
        "monthly_avg": monthly_avg,
        "current_month_revenue": current_month_revenue,
        "current_year_revenue": current_year_revenue,
        "monthly_target": monthly_target,
        "annual_target": annual_target,
        "monthly_pct": (current_month_revenue / monthly_target * 100.0) if monthly_target else None,
        "annual_pct": (current_year_revenue / annual_target * 100.0) if annual_target else None,
        "current_year": current_year,
        "current_month_label": current_month_key,
        "objectives_available": objectives_available,
    }


def _division_visit_ranking(division, limit=5):
    """Classement métier des visites : Prospection est la source de vérité."""
    return (
        db.session.query(
            User.username,
            User.zone,
            func.count(Prospection.id).label("nombre_visites"),
        )
        .join(Prospection, Prospection.commercial_id == User.id)
        .filter(User.project == division, User.role == "commercial")
        .group_by(User.id, User.username, User.zone)
        .order_by(func.count(Prospection.id).desc(), User.username.asc())
        .limit(limit)
        .all()
    )


def _division_dashboard(division, template_name):
    _ensure_division_access(division)
    prospections = Prospection.query.join(User).filter(User.project == division).order_by(Prospection.date.desc()).all()
    if not prospections:
        flash(f"Aucune donnée trouvée pour {division.upper()}.", "info")
    labels, totals, _ = _monthly_revenue_for_division(division)
    objectives_kpis = _objectives_kpis(division, labels, totals)
    top_5_commerciaux = _division_visit_ranking(division)
    commerciaux = User.query.filter_by(project=division, role="commercial").order_by(User.username).all()
    suppliers = _division_suppliers(division)
    return render_template(template_name, monthly_revenue_labels=labels, monthly_revenue_data=totals,
                           top_5_commerciaux=top_5_commerciaux, commerciaux=commerciaux,
                           prospections=prospections, suppliers=suppliers, division=division, kpis=objectives_kpis)


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
    rows = []
    for month in labels:
        values = {slug: combined[month].get(slug, 0.0) for slug, *_ in suppliers}
        rows.append({"month": month, "amounts": values, "total": sum(values.values())})
    kpis = _objectives_kpis(division, labels, totals)
    return render_template(template_name, rows=rows, suppliers=suppliers, kpis=kpis, division=division, monthly_revenue_labels=labels)


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


def _month_bounds(month):
    """Retourne les bornes [début, fin) d'un mois YYYY-MM validé."""
    try:
        parsed = datetime.strptime(month, "%Y-%m")
    except ValueError:
        abort(404)
    start = date(parsed.year, parsed.month, 1)
    if parsed.month == 12:
        end = date(parsed.year + 1, 1, 1)
    else:
        end = date(parsed.year, parsed.month + 1, 1)
    return start, end


def _product_sales_detail(sale_model, product_model, month):
    """Agrège le détail produit du mois directement en SQL."""
    start, end = _month_bounds(month)
    amount_expr = func.coalesce(sale_model.quantity, 0) * func.coalesce(sale_model.price, 0)
    rows = (
        db.session.query(
            product_model.name,
            func.coalesce(func.sum(sale_model.quantity), 0).label("total_quantity"),
            func.coalesce(func.sum(amount_expr), 0).label("total_revenue"),
        )
        .join(sale_model, sale_model.product_id == product_model.id)
        .filter(sale_model.date >= start, sale_model.date < end)
        .group_by(product_model.id, product_model.name)
        .order_by(product_model.name.asc())
        .all()
    )
    return [
        ProductSaleRow(name=name, total_quantity=quantity, total_revenue=float(revenue or 0))
        for name, quantity, revenue in rows
    ]


def _monthly_revenue_detail_route(division, month, template_name):
    _ensure_division_access(division)
    suppliers = _division_suppliers(division)
    details = {slug: _product_sales_detail(sale_model, product_model, month) for slug, _label, sale_model, product_model in suppliers}
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
