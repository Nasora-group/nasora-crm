from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models import DIVISION_SUPPLIERS, SUPPLIERS
from app.models_stock import StockEntry
from app.permissions import is_admin, require_division
from app.utils import roles_required

v2_products_bp = Blueprint("v2_products", __name__, url_prefix="/v2/produits")


def _bounds(month):
    try:
        start = datetime.strptime(month, "%Y-%m").date()
    except (TypeError, ValueError):
        start = date.today().replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _catalog_rows(division, month):
    require_division(division)
    start, end = _bounds(month)
    rows = {}
    for slug in DIVISION_SUPPLIERS.get(division, []):
        supplier = SUPPLIERS[slug]
        product_model, sale_model = supplier["product_model"], supplier["sale_model"]
        sales = (
            db.session.query(
                product_model.name,
                func.coalesce(func.sum(sale_model.quantity), 0).label("qty"),
                func.coalesce(func.sum(sale_model.quantity * sale_model.price), 0).label("revenue"),
            )
            .join(sale_model, sale_model.product_id == product_model.id)
            .filter(sale_model.project == division, sale_model.date >= start, sale_model.date < end)
            .group_by(product_model.id, product_model.name)
            .all()
        )
        for name, qty, revenue in sales:
            key = (slug, name)
            rows.setdefault(key, {
                "division": division, "laboratory": supplier["label"], "product": name,
                "quantity": 0, "revenue": Decimal("0"), "stocks": {},
            })
            rows[key]["quantity"] += int(qty or 0)
            rows[key]["revenue"] += Decimal(str(revenue or 0))
        products = product_model.query.filter_by(is_active=True).all()
        for product in products:
            key = (slug, product.name)
            rows.setdefault(key, {
                "division": division, "laboratory": supplier["label"], "product": product.name,
                "quantity": 0, "revenue": Decimal("0"), "stocks": {},
            })
            rows[key]["reference"] = product.reference
            rows[key]["price"] = Decimal(str(product.default_price or 0))
    week = start - timedelta(days=start.weekday())
    latest = {}
    while week < end:
        week_end = week
        entries = StockEntry.query.filter_by(week_start=week_end, division=division).all()
        for e in entries:
            latest[(e.laboratory, e.product_name, e.wholesaler)] = e.quantity
        week = week.fromordinal(week.toordinal() + 7)
    for row in rows.values():
        keylab = row["laboratory"]
        keyprod = row["product"]
        quantities = {w: q for (lab, prod, w), q in latest.items() if lab == keylab and prod == keyprod}
        row["stocks"] = quantities
        row["ruptures"] = sum(1 for q in quantities.values() if q <= 0)
        row["low_stocks"] = sum(1 for q in quantities.values() if 0 < q <= 10)
        row["total_stock"] = sum(quantities.values())
    return sorted(rows.values(), key=lambda x: (-float(x["revenue"]), x["product"].lower()))


@v2_products_bp.route("")
@login_required
@roles_required("admin")
def index():
    division = (request.args.get("division") or "nasmedic").lower()
    if division not in DIVISION_SUPPLIERS:
        division = "nasmedic"
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    rows = _catalog_rows(division, month)
    total_revenue = sum(float(r["revenue"]) for r in rows)
    total_quantity = sum(r["quantity"] for r in rows)
    rupture_count = sum(r["ruptures"] for r in rows)
    low_count = sum(r["low_stocks"] for r in rows)
    return render_template("v2/products.html", rows=rows, division=division, month=month,
                           total_revenue=total_revenue, total_quantity=total_quantity,
                           rupture_count=rupture_count, low_count=low_count,
                           wholesalers=("duopharm", "ubipharm", "laborex", "sodipharm"))


@v2_products_bp.route("/ruptures")
@login_required
@roles_required("admin")
def ruptures():
    division = (request.args.get("division") or "nasmedic").lower()
    if division not in DIVISION_SUPPLIERS:
        division = "nasmedic"
    rows = _catalog_rows(division, request.args.get("month") or date.today().strftime("%Y-%m"))
    critical = [r for r in rows if r["ruptures"] or r["low_stocks"]]
    return render_template("v2/product_ruptures.html", rows=critical, division=division)
