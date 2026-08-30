from datetime import date, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

from app.extensions import db
from app.models import DIVISION_SUPPLIERS, SUPPLIERS
from app.models_stock import StockEntry
from app.utils import roles_required

stock_bp = Blueprint("stock", __name__, url_prefix="/stock")
WHOLESALERS = {
    "duopharm": "DUOPHARM",
    "sodipharm": "SODIPHARM",
    "laborex": "LABOREX",
    "ubipharm": "UBIPHARM (COPHASE)",
}


def _monday(value):
    return value - timedelta(days=value.weekday())


def _products():
    names = set()
    for slugs in DIVISION_SUPPLIERS.values():
        for slug in slugs:
            model = SUPPLIERS[slug]["product_model"]
            names.update(name for (name,) in model.query.filter_by(is_active=True).with_entities(model.name).all())
    return sorted(names, key=str.casefold)


def _status(quantity):
    if quantity <= 0:
        return "rupture", "Rupture"
    if quantity <= 10:
        return "faible", "Stock faible"
    return "disponible", "Disponible"


def _snapshot(week_start):
    entries = StockEntry.query.filter_by(week_start=week_start).all()
    return {(entry.wholesaler, entry.product_name): entry for entry in entries}


@stock_bp.route("/disponible")
@login_required
def available():
    week = request.args.get("week", "")
    try:
        selected = date.fromisoformat(week) if week else date.today()
    except ValueError:
        selected = date.today()
    week_start = _monday(selected)
    products = _products()
    entries = _snapshot(week_start)
    rows = []
    for product in products:
        stocks = {}
        for slug in WHOLESALERS:
            entry = entries.get((slug, product))
            quantity = entry.quantity if entry else 0
            status, label = _status(quantity)
            stocks[slug] = {"quantity": quantity, "status": status, "label": label}
        rows.append({"product": product, "stocks": stocks})
    return render_template("stock_available.html", rows=rows, week_start=week_start, wholesalers=WHOLESALERS, is_admin=current_user.role == "admin")


@stock_bp.route("/saisie", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def entry():
    raw_week = request.form.get("week_start") or request.args.get("week_start") or ""
    try:
        week_start = _monday(date.fromisoformat(raw_week)) if raw_week else _monday(date.today())
    except ValueError:
        week_start = _monday(date.today())
    products = _products()
    if request.method == "POST":
        try:
            validate_csrf(request.form.get("csrf_token"))
            for product in products:
                for slug in WHOLESALERS:
                    key = f"stock__{slug}__{product}"
                    raw = request.form.get(key, "0").strip()
                    quantity = max(0, int(raw or 0))
                    item = StockEntry.query.filter_by(week_start=week_start, wholesaler=slug, product_name=product).first()
                    if item is None:
                        item = StockEntry(week_start=week_start, wholesaler=slug, product_name=product, created_by_id=current_user.id)
                        db.session.add(item)
                    item.quantity = quantity
            db.session.commit()
            flash(f"Stocks de la semaine du {week_start.strftime('%d/%m/%Y')} enregistrés.", "success")
            return redirect(url_for("stock.available", week=week_start.isoformat()))
        except (ValueError, ValidationError):
            db.session.rollback()
            flash("Une quantité de stock est invalide. Utilisez uniquement des nombres entiers positifs.", "error")
        except Exception:
            db.session.rollback()
            flash("Impossible d'enregistrer les stocks pour le moment.", "error")
    entries = _snapshot(week_start)
    return render_template("stock_entry.html", products=products, wholesalers=WHOLESALERS, week_start=week_start, entries=entries)


@stock_bp.route("/historique")
@login_required
@roles_required("admin")
def history():
    weeks = [week for (week,) in db.session.query(StockEntry.week_start).distinct().order_by(StockEntry.week_start.desc()).all()]
    return render_template("stock_history.html", weeks=weeks, wholesalers=WHOLESALERS)
