import csv
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from flask import Blueprint, render_template, request, Response
from flask_login import login_required

from sqlalchemy import func

from app.extensions import db
from app.models import (
    User, Prospection, Planning, AnimationSale,
    DIVISION_SUPPLIERS, SUPPLIERS
)
from app.models_clients import ClientVisit
from app.models_stock import StockEntry
from app.utils import roles_required

reports_bp = Blueprint("v2_reports", __name__, url_prefix="/v2/rapports")


def _date_range():
    start_raw = (request.args.get("date_start") or "").strip()
    end_raw = (request.args.get("date_end") or "").strip()
    try:
        start = date.fromisoformat(start_raw) if start_raw else date.today().replace(day=1)
    except ValueError:
        start = date.today().replace(day=1)
    try:
        end = date.fromisoformat(end_raw) if end_raw else date.today()
    except ValueError:
        end = date.today()
    if end < start:
        start, end = end, start
    return start, end


def _sales_rows(start, end, division="all"):
    rows = []
    for slug, supplier in SUPPLIERS.items():
        if supplier.get("archived"):
            continue
        if division != "all" and supplier["division"] != division:
            continue
        model = supplier["sale_model"]
        product_model = supplier["product_model"]
        query = (
            db.session.query(model, product_model.name.label("product_name"))
            .join(product_model, model.product_id == product_model.id)
            .filter(model.date >= start, model.date <= end)
        )
        for sale, product_name in query.all():
            rows.append({
                "date": sale.date,
                "division": supplier["division"],
                "laboratory": supplier["label"],
                "product": product_name,
                "quantity": sale.quantity,
                "revenue": Decimal(str(sale.quantity or 0)) * Decimal(str(sale.price or 0)),
                "user_id": sale.commercial_id,
            })
    return rows


@reports_bp.route("")
@login_required
@roles_required("admin")
def index():
    start, end = _date_range()
    division = (request.args.get("division") or "all").strip().lower()
    if division not in {"all", *DIVISION_SUPPLIERS.keys()}:
        division = "all"
    sales = _sales_rows(start, end, division)
    prospection_query = Prospection.query.filter(Prospection.date.between(start, end))
    visit_query = ClientVisit.query.filter(
        ClientVisit.date.between(start, end),
        ClientVisit.is_duplicate.is_(False),
    )
    if division != "all":
        prospection_query = prospection_query.join(User, Prospection.commercial_id == User.id).filter(User.project == division)
        visit_query = visit_query.join(User, ClientVisit.commercial_id == User.id).filter(User.project == division)

    animations = AnimationSale.query.filter(
        AnimationSale.animation_date >= start,
        AnimationSale.animation_date <= end,
    )
    if division != "all":
        animations = animations.filter(AnimationSale.project == division)
    animations = animations.order_by(AnimationSale.animation_date.desc()).all()
    return render_template(
        "v2/reports.html",
        date_start=start.isoformat(),
        date_end=end.isoformat(),
        division=division,
        sales_count=len(sales),
        sales_revenue=sum((r["revenue"] for r in sales), Decimal("0.00")),
        prospections=prospection_query.count(),
        visits=visit_query.count(),
        animation_lines=len(animations),
        animation_revenue=sum((a.total_amount for a in animations), Decimal("0.00")),
        animations=animations[:20],
    )


def _csv_response(filename, headers, rows):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@reports_bp.route("/export/ventes.csv")
@login_required
@roles_required("admin")
def export_sales():
    start, end = _date_range()
    division = (request.args.get("division") or "all").strip().lower()
    rows = _sales_rows(start, end, division)
    users = {u.id: u.username for u in User.query.all()}
    return _csv_response(
        "nasora_v2_ventes.csv",
        ["Date", "Division", "Laboratoire", "Produit", "Quantité", "CA FCFA", "Utilisateur"],
        [[r["date"], r["division"], r["laboratory"], r["product"], r["quantity"], r["revenue"], users.get(r["user_id"], "")] for r in rows],
    )


@reports_bp.route("/export/animations.csv")
@login_required
@roles_required("admin")
def export_animations():
    start, end = _date_range()
    division = (request.args.get("division") or "all").strip().lower()
    query = AnimationSale.query.filter(AnimationSale.animation_date.between(start, end))
    if division != "all":
        query = query.filter(AnimationSale.project == division)
    rows = query.order_by(AnimationSale.animation_date.desc(), AnimationSale.id.desc()).all()
    users = {u.id: u.username for u in User.query.filter_by(role="animateur").all()}
    return _csv_response(
        "nasora_v2_animations.csv",
        ["Date", "Division", "Animateur", "Pharmacie", "Produit", "Quantité", "Prix unitaire FCFA", "CA FCFA"],
        [[r.animation_date, r.project, users.get(r.animateur_id, ""), r.pharmacy_name, r.product_name, r.quantity, r.unit_price, r.total_amount] for r in rows],
    )


@reports_bp.route("/export/activite.csv")
@login_required
@roles_required("admin")
def export_activity():
    start, end = _date_range()
    division = (request.args.get("division") or "all").strip().lower()
    prospection_query = Prospection.query.filter(Prospection.date.between(start, end))
    visit_query = ClientVisit.query.filter(
        ClientVisit.date.between(start, end),
        ClientVisit.is_duplicate.is_(False),
    )
    if division in DIVISION_SUPPLIERS:
        prospection_query = prospection_query.join(User, Prospection.commercial_id == User.id).filter(User.project == division)
        visit_query = visit_query.join(User, ClientVisit.commercial_id == User.id).filter(User.project == division)
    prospections = prospection_query.all()
    visits = visit_query.all()
    users = {u.id: u.username for u in User.query.all()}
    return _csv_response(
        "nasora_v2_activite.csv",
        ["Type", "Date", "Utilisateur", "Professionnel", "Structure", "Détails"],
        (
            [["Prospection", p.date, users.get(p.commercial_id, ""), p.nom_client, p.structure, p.establishment or ""] for p in prospections]
            + [["Visite réelle", v.date, users.get(v.commercial_id, ""), "", "", (v.report or "")] for v in visits]
        ),
    )


@reports_bp.route("/export/stocks.csv")
@login_required
@roles_required("admin")
def export_stocks():
    start, end = _date_range()
    rows = StockEntry.query.filter(StockEntry.week_start.between(start, end))
    division = (request.args.get("division") or "all").strip().lower()
    if division != "all":
        rows = rows.filter(StockEntry.division == division)
    rows = rows.order_by(StockEntry.week_start.desc(), StockEntry.division, StockEntry.product_name).all()
    return _csv_response(
        "nasora_v2_stocks.csv",
        ["Semaine", "Division", "Laboratoire", "Grossiste", "Produit", "Quantité"],
        [[r.week_start, r.division, r.laboratory, r.wholesaler, r.product_name, r.quantity] for r in rows],
    )
