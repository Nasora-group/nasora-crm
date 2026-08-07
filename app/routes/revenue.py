from collections import namedtuple

from flask import Blueprint, render_template, flash, request
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db, cache
from app.models import (
    User, Prospection,
    NovaPharmaSale, GilbertSale, EricFavreSale, TroisCheneSale,
    NovaPharmaProduct, GilbertProduct, EricFavreProduct, TroisCheneProduct,
)
from app.utils import roles_required

revenue_bp = Blueprint("revenue", __name__)

DIVISION_SALE_MODELS = {
    "nasderm": [("nova_pharma", NovaPharmaSale, NovaPharmaProduct), ("gilbert", GilbertSale, GilbertProduct)],
    "nasmedic": [("eric_favre", EricFavreSale, EricFavreProduct), ("trois_chene", TroisCheneSale, TroisCheneProduct)],
}

ProductSaleRow = namedtuple("ProductSaleRow", ["name", "total_quantity", "total_revenue"])


def _monthly_revenue_for_division(division):
    """Combine le CA mensuel des deux fournisseurs d'une division.
    Le regroupement par mois se fait en Python (et non via une fonction SQL
    comme strftime) pour rester compatible avec SQLite (dev) ET PostgreSQL
    (production), qui n'a pas de fonction strftime()."""
    combined = {}
    for slug, sale_model, _ in DIVISION_SALE_MODELS[division]:
        rows = (
            db.session.query(sale_model.date, sale_model.quantity, sale_model.price)
            .filter(sale_model.project == division)
            .all()
        )
        for sale_date, quantity, price in rows:
            month = sale_date.strftime("%Y-%m")
            combined.setdefault(month, {}).setdefault(slug, 0)
            combined[month][slug] += (quantity or 0) * (price or 0)

    labels = sorted(combined.keys())
    totals = [sum(combined[m].values()) for m in labels]
    return labels, totals, combined


def _division_dashboard(division, template_name):
    prospections = (
        Prospection.query.join(User).filter(User.project == division).order_by(Prospection.date.desc()).all()
    )
    if not prospections:
        flash(f"Aucune donnée trouvée pour {division.upper()}.", "info")

    labels, totals, _ = _monthly_revenue_for_division(division)

    top_5_commerciaux = (
        db.session.query(User.username, User.zone, func.count(Prospection.id).label("nombre_visites"))
        .join(Prospection)
        .filter(User.project == division)
        .group_by(User.id)
        .order_by(func.count(Prospection.id).desc())
        .limit(5)
        .all()
    )

    commerciaux = User.query.filter_by(project=division, role="commercial").order_by(User.username).all()

    return render_template(
        template_name,
        monthly_revenue_labels=labels,
        monthly_revenue_data=totals,
        top_5_commerciaux=top_5_commerciaux,
        commerciaux=commerciaux,
        prospections=prospections,
    )


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


@revenue_bp.route("/monthly_revenue_nasderm")
@login_required
@roles_required("admin", "commercial")
def monthly_revenue_nasderm():
    _, _, combined = _monthly_revenue_for_division("nasderm")
    monthly_revenue = [
        (month, combined[month].get("nova_pharma", 0), combined[month].get("gilbert", 0),
         sum(combined[month].values()))
        for month in sorted(combined.keys())
    ]
    return render_template("monthly_revenue_nasderm.html", monthly_revenue=monthly_revenue)


@revenue_bp.route("/monthly_revenue_nasmedic")
@login_required
@roles_required("admin", "commercial")
def monthly_revenue_nasmedic():
    _, _, combined = _monthly_revenue_for_division("nasmedic")
    monthly_revenue = [
        (month, combined[month].get("eric_favre", 0), combined[month].get("trois_chene", 0),
         sum(combined[month].values()))
        for month in sorted(combined.keys())
    ]
    return render_template("monthly_revenue_nasmedic.html", monthly_revenue=monthly_revenue)


def _product_sales_detail(sale_model, product_model, month):
    """Regroupement par produit pour un mois donné, calculé en Python pour
    rester compatible SQLite/PostgreSQL (voir _monthly_revenue_for_division)."""
    rows = (
        db.session.query(product_model.name, sale_model.quantity, sale_model.price, sale_model.date)
        .join(sale_model, sale_model.product_id == product_model.id)
        .all()
    )
    aggregated = {}
    for name, quantity, price, sale_date in rows:
        if sale_date.strftime("%Y-%m") != month:
            continue
        agg = aggregated.setdefault(name, {"total_quantity": 0, "total_revenue": 0})
        agg["total_quantity"] += quantity or 0
        agg["total_revenue"] += (quantity or 0) * (price or 0)

    return [
        ProductSaleRow(name=name, total_quantity=values["total_quantity"], total_revenue=values["total_revenue"])
        for name, values in aggregated.items()
    ]


@revenue_bp.route("/monthly_revenue_detail_nasderm/<month>")
@login_required
@roles_required("admin", "commercial")
def monthly_revenue_detail_nasderm(month):
    nova_pharma_sales = _product_sales_detail(NovaPharmaSale, NovaPharmaProduct, month)
    gilbert_sales = _product_sales_detail(GilbertSale, GilbertProduct, month)
    return render_template(
        "monthly_revenue_detail_nasderm.html",
        month=month,
        nova_pharma_sales=nova_pharma_sales,
        gilbert_sales=gilbert_sales,
    )


@revenue_bp.route("/monthly_revenue_detail_nasmedic/<month>")
@login_required
@roles_required("admin", "commercial")
def monthly_revenue_detail_nasmedic(month):
    eric_favre_sales = _product_sales_detail(EricFavreSale, EricFavreProduct, month)
    trois_chene_sales = _product_sales_detail(TroisCheneSale, TroisCheneProduct, month)
    return render_template(
        "monthly_revenue_detail_nasmedic.html",
        month=month,
        eric_favre_sales=eric_favre_sales,
        trois_chene_sales=trois_chene_sales,
    )
