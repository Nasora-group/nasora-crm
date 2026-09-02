from datetime import date, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError
from sqlalchemy import false
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import DIVISION_SUPPLIERS, SUPPLIERS
from app.models_stock import StockEntry
from app.utils import roles_required

stock_bp = Blueprint("stock", __name__, url_prefix="/stock")
WHOLESALERS = {"duopharm": "DUOPHARM", "sodipharm": "SODIPHARM", "laborex": "LABOREX", "ubipharm": "UBIPHARM (COPHASE)"}


def _monday(value):
    return value - timedelta(days=value.weekday())


def _allowed_divisions():
    if current_user.role == "admin":
        return ("nasmedic", "nasderm")
    division = (current_user.project or "").strip().lower()
    return (division,) if division in DIVISION_SUPPLIERS else ()


def _catalog():
    catalog = []
    for division in _allowed_divisions():
        for slug in DIVISION_SUPPLIERS.get(division, []):
            # NASDERM est exploité avec Gilbert. Cette règle doit être
            # appliquée côté serveur et pas seulement par l'interface afin
            # qu'un fournisseur NASDERM archivé/non autorisé ne puisse jamais
            # réapparaître dans une nouvelle saisie de stock.
            if division == "nasderm" and slug != "gilbert":
                continue
            supplier = SUPPLIERS[slug]
            model = supplier["product_model"]
            for product in model.query.filter_by(is_active=True).order_by(model.name).all():
                catalog.append({"division": division, "laboratory": supplier["label"], "product": product.name})
    return catalog


def _status(quantity):
    if quantity <= 0:
        return "rupture", "Rupture"
    if quantity <= 10:
        return "faible", "Stock faible"
    return "disponible", "Disponible"


def _snapshot(week_start):
    query = StockEntry.query.filter_by(week_start=week_start)
    allowed = _allowed_divisions()
    query = query.filter(StockEntry.division.in_(allowed)) if allowed else query.filter(false())
    return {(e.division, e.laboratory, e.wholesaler, e.product_name): e for e in query.all()}


def _save_stock_entry(item, slug, week_start, quantity):
    """Crée ou met à jour une ligne sans laisser une course concurrente annuler toute la saisie."""
    filters = {
        "week_start": week_start,
        "division": item["division"],
        "laboratory": item["laboratory"],
        "wholesaler": slug,
        "product_name": item["product"],
    }
    stock = StockEntry.query.filter_by(**filters).first()
    if stock is not None:
        stock.quantity = quantity
        return

    try:
        with db.session.begin_nested():
            db.session.add(
                StockEntry(
                    **filters,
                    quantity=quantity,
                    created_by_id=current_user.id,
                )
            )
            db.session.flush()
    except IntegrityError:
        stock = StockEntry.query.filter_by(**filters).first()
        if stock is None:
            raise
        stock.quantity = quantity


@stock_bp.route("/disponible")
@login_required
def available():
    week = request.args.get("week", "")
    try:
        selected = date.fromisoformat(week) if week else date.today()
    except ValueError:
        selected = date.today()
    week_start = _monday(selected)
    entries = _snapshot(week_start)

    # Le catalogue ne contient que les produits actifs. Pour une semaine
    # historique, les lignes déjà saisies doivent toutefois rester visibles
    # même si le produit ou le fournisseur a ensuite été désactivé/archivé.
    catalog = _catalog()
    catalog_keys = {(item["division"], item["laboratory"], item["product"]) for item in catalog}
    for division, laboratory, _wholesaler, product in entries:
        key = (division, laboratory, product)
        if key not in catalog_keys:
            catalog.append({"division": division, "laboratory": laboratory, "product": product})
            catalog_keys.add(key)

    grouped = {}
    for item in catalog:
        key = (item["division"], item["laboratory"])
        row = grouped.setdefault(key, {"division": item["division"], "laboratory": item["laboratory"], "products": []})
        stocks = {}
        for slug in WHOLESALERS:
            entry = entries.get((item["division"], item["laboratory"], slug, item["product"]))
            quantity = entry.quantity if entry else 0
            status, label = _status(quantity)
            stocks[slug] = {"quantity": quantity, "status": status, "label": label}
        row["products"].append({"product": item["product"], "stocks": stocks})
    return render_template("stock_available.html", groups=list(grouped.values()), week_start=week_start, wholesalers=WHOLESALERS, is_admin=current_user.role == "admin", allowed_divisions=_allowed_divisions())


@stock_bp.route("/saisie", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def entry():
    raw_week = request.form.get("week_start") or request.args.get("week_start") or ""
    try:
        week_start = _monday(date.fromisoformat(raw_week)) if raw_week else _monday(date.today())
    except ValueError:
        week_start = _monday(date.today())
    catalog = _catalog()

    if request.method == "POST" and "change_week" in request.form:
        return redirect(url_for("stock.entry", week_start=week_start.isoformat()))

    if request.method == "POST":
        try:
            validate_csrf(request.form.get("csrf_token"))
            for item in catalog:
                for slug in WHOLESALERS:
                    key = f"stock__{item['division']}__{item['laboratory']}__{slug}__{item['product']}"
                    raw_quantity = request.form.get(key, "0").strip() or "0"
                    quantity = int(raw_quantity)
                    if quantity < 0:
                        raise ValueError("negative stock quantity")
                    _save_stock_entry(item, slug, week_start, quantity)
            db.session.commit()
            flash(f"Stocks de la semaine du {week_start.strftime('%d/%m/%Y')} enregistrés.", "success")
            return redirect(url_for("stock.available", week=week_start.isoformat()))
        except (ValueError, ValidationError):
            db.session.rollback()
            flash("Une quantité de stock est invalide. Utilisez uniquement des nombres entiers positifs ou nuls.", "error")
        except Exception:
            db.session.rollback()
            flash("Impossible d'enregistrer les stocks pour le moment.", "error")
    entries = _snapshot(week_start)
    return render_template("stock_entry.html", catalog=catalog, wholesalers=WHOLESALERS, week_start=week_start, entries=entries)


@stock_bp.route("/historique")
@login_required
@roles_required("admin")
def history():
    weeks = [week for (week,) in db.session.query(StockEntry.week_start).filter(StockEntry.division.in_(_allowed_divisions())).distinct().order_by(StockEntry.week_start.desc()).all()]
    return render_template("stock_history.html", weeks=weeks, wholesalers=WHOLESALERS)
