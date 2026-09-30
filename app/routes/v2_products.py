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
            .filter(
                sale_model.project == division,
                sale_model.date >= start,
                sale_model.date < end,
            )
            .group_by(product_model.id, product_model.name)
            .all()
        )
        for name, qty, revenue in sales:
            key = (slug, name)
            rows.setdefault(key, {
                "division": division,
                "laboratory": supplier["label"],
                "product": name,
                "quantity": 0,
                "revenue": Decimal("0"),
                "stocks": {},
            })
            rows[key]["quantity"] += int(qty or 0)
            rows[key]["revenue"] += Decimal(str(revenue or 0))

        products = product_model.query.filter_by(is_active=True).all()
        for product in products:
            key = (slug, product.name)
            rows.setdefault(key, {
                "division": division,
                "laboratory": supplier["label"],
                "product": product.name,
                "quantity": 0,
                "revenue": Decimal("0"),
                "stocks": {},
            })
            rows[key]["reference"] = product.reference
            rows[key]["price"] = Decimal(str(product.default_price or 0))

    first_week = start - timedelta(days=start.weekday())
    latest = {}
    week = first_week
    while week < end:
        week = week.fromordinal(week.toordinal() + 7)

    entries = (
        StockEntry.query
        .filter(
            StockEntry.week_start >= first_week,
            StockEntry.week_start < end,
            StockEntry.division == division,
        )
        .order_by(StockEntry.week_start.asc())
        .all()
    )
    for entry in entries:
        latest[(entry.laboratory, entry.product_name, entry.wholesaler)] = entry.quantity

    for row in rows.values():
        prefix = (row["laboratory"], row["product"])
        quantities = {
            wholesaler: quantity
            for (laboratory, product, wholesaler), quantity in latest.items()
            if (laboratory, product) == prefix
        }
        row["stocks"] = quantities
        row["ruptures"] = sum(1 for quantity in quantities.values() if quantity <= 0)
        row["low_stocks"] = sum(1 for quantity in quantities.values() if 0 < quantity <= 10)
        row["total_stock"] = sum(quantities.values())

    return sorted(
        rows.values(),
        key=lambda x: (-float(x["revenue"]), x["product"].lower()),
    )


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
    return render_template(
        "v2/products.html",
        rows=rows,
        division=division,
        month=month,
        total_revenue=total_revenue,
        total_quantity=total_quantity,
        rupture_count=rupture_count,
        low_count=low_count,
        wholesalers=("duopharm", "ubipharm", "laborex", "sodipharm"),
    )


@v2_products_bp.route("/ruptures")
@login_required
@roles_required("admin")
def ruptures():
    division = (request.args.get("division") or "nasmedic").lower()
    if division not in DIVISION_SUPPLIERS:
        division = "nasmedic"
    rows = _catalog_rows(
        division,
        request.args.get("month") or date.today().strftime("%Y-%m"),
    )
    critical = [r for r in rows if r["ruptures"] or r["low_stocks"]]
    return render_template(
        "v2/product_ruptures.html",
        rows=critical,
        division=division,
    )


@v2_products_bp.route("/reassorts")
@login_required
@roles_required("admin")
def reassorts():
    division = (request.args.get("division") or "nasmedic").lower()
    if division not in DIVISION_SUPPLIERS:
        division = "nasmedic"
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    rows = _catalog_rows(division, month)
    priorities = []
    for row in rows:
        affected = [
            wholesaler
            for wholesaler, quantity in row["stocks"].items()
            if quantity <= 10
        ]
        if not affected:
            continue
        priorities.append({
            **row,
            "priority": "Urgent" if any(row["stocks"][w] <= 0 for w in affected) else "À réapprovisionner",
            "affected_wholesalers": affected,
        })
    priorities.sort(
        key=lambda row: (
            0 if row["priority"] == "Urgent" else 1,
            -row["ruptures"],
            -row["low_stocks"],
            row["product"].lower(),
        )
    )
    return render_template(
        "v2/product_reassorts.html",
        rows=priorities,
        division=division,
        month=month,
    )
