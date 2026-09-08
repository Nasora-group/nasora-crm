from datetime import datetime
from decimal import Decimal, InvalidOperation
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import User, get_active_products_for_division, get_active_product_prices_for_division
from app.utils import roles_required


animation_sales_bp = Blueprint("animation_sales", __name__, url_prefix="/animations/ventes")


def _render_sale_form(products, prices, form_data):
    return render_template("animation_sale_form.html", products=products, prices=prices, form_data=form_data)


@animation_sales_bp.route("/nouvelle", methods=["GET", "POST"])
@login_required
@roles_required("admin", "commercial", "animateur")
def new_animation_sale():
    """Create an animation sale with quantity and sale unit price entered per product."""
    if current_user.role not in {"animateur", "admin"}:
        abort(403)

    division = (current_user.project or "").strip().lower()
    products = get_active_products_for_division(division)
    prices = get_active_product_prices_for_division(division)

    if request.method == "POST":
        pharmacy = (request.form.get("pharmacy_name") or "").strip()
        raw_date = (request.form.get("animation_date") or "").strip()
        if not pharmacy or not raw_date:
            flash("Le nom de la pharmacie et la date d'animation sont obligatoires.", "error")
            return _render_sale_form(products, prices, request.form)

        try:
            animation_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            flash("La date d'animation est invalide.", "error")
            return _render_sale_form(products, prices, request.form)

        items = []
        invalid_product = None
        for product_name in products:
            raw_quantity = (request.form.get(f"quantity__{product_name}") or "").strip()
            raw_price = (request.form.get(f"unit_price__{product_name}") or "").strip().replace(",", ".")

            if not raw_quantity and not raw_price:
                continue

            try:
                quantity = int(raw_quantity)
                unit_price = Decimal(raw_price)
                if quantity <= 0 or unit_price < 0:
                    raise ValueError
                unit_price = unit_price.quantize(Decimal("0.01"))
            except (ValueError, TypeError, InvalidOperation, ArithmeticError):
                invalid_product = product_name
                break

            items.append((product_name, quantity, unit_price))

        if invalid_product:
            flash(f"La quantité et le prix unitaire de « {invalid_product} » doivent être valides.", "error")
            return _render_sale_form(products, prices, request.form)

        if not items:
            flash("Sélectionnez au moins un produit et renseignez sa quantité et son prix unitaire.", "error")
            return _render_sale_form(products, prices, request.form)

        from app.models import AnimationSale
        try:
            for product_name, quantity, unit_price in items:
                db.session.add(AnimationSale(
                    animateur_id=current_user.id,
                    pharmacy_name=pharmacy,
                    animation_date=animation_date,
                    product_name=product_name,
                    quantity=quantity,
                    unit_price=unit_price,
                    project=division,
                ))
            db.session.commit()
            flash(f"Animation enregistrée : {len(items)} produit(s) vendu(s).", "success")
            return redirect(url_for("animation_sales.my_history"))
        except Exception:
            db.session.rollback()
            flash("Impossible d'enregistrer les ventes de l'animation.", "error")
            return _render_sale_form(products, prices, request.form)

    return _render_sale_form(products, prices, {})


def _animation_sales_query():
    """Return the animation sales query restricted to the current user's scope."""
    from app.models import AnimationSale

    query = AnimationSale.query
    if current_user.role == "animateur":
        query = query.filter_by(animateur_id=current_user.id)
    elif current_user.role != "admin":
        query = query.filter_by(project=(current_user.project or "").strip().lower())
    return query


@animation_sales_bp.route("/historique")
@login_required
@roles_required("admin", "commercial", "animateur")
def my_history():
    from app.models import AnimationSale

    selected_month = (request.args.get("month") or "").strip()
    month_date = None
    if selected_month:
        try:
            month_date = datetime.strptime(selected_month, "%Y-%m").date()
        except ValueError:
            selected_month = ""

    query = _animation_sales_query()
    if month_date:
        if month_date.month == 12:
            next_month = month_date.replace(year=month_date.year + 1, month=1, day=1)
        else:
            next_month = month_date.replace(month=month_date.month + 1, day=1)
        query = query.filter(
            AnimationSale.animation_date >= month_date,
            AnimationSale.animation_date < next_month,
        )

    sales = query.order_by(AnimationSale.animation_date.desc(), AnimationSale.id.desc()).all()

    by_date = {}
    for sale in sales:
        by_date.setdefault(sale.animation_date, []).append(sale)

    days = []
    for animation_date, items in by_date.items():
        days.append({
            "animation_date": animation_date,
            "items": items,
            "animateurs": sorted({
                sale.animateur.username if sale.animateur else "-"
                for sale in items
            }),
            "total_quantity": sum(i.quantity for i in items),
            "total_amount": sum((i.total_amount for i in items), Decimal("0.00")),
        })

    general_total = sum((day["total_amount"] for day in days), Decimal("0.00"))
    general_quantity = sum(day["total_quantity"] for day in days)

    return render_template(
        "animation_sales_history.html",
        days=days,
        general_total=general_total,
        general_quantity=general_quantity,
        selected_month=selected_month,
        is_admin=current_user.role == "admin",
        current_user_id=current_user.id,
    )


@animation_sales_bp.route("/<int:sale_id>/modifier", methods=["GET", "POST"])
@login_required
@roles_required("admin", "animateur")
def edit_animation_sale(sale_id):
    """Edit an animation sale: animateur only own sale; admin any sale."""
    from app.models import AnimationSale

    sale = AnimationSale.query.get_or_404(sale_id)

    if current_user.role == "animateur" and sale.animateur_id != current_user.id:
        abort(403)
    if current_user.role not in {"animateur", "admin"}:
        abort(403)

    if request.method == "POST":
        raw_quantity = (request.form.get("quantity") or "").strip()
        raw_price = (request.form.get("unit_price") or "").strip().replace(",", ".")

        try:
            quantity = int(raw_quantity)
            if quantity <= 0:
                raise ValueError
            unit_price = Decimal(raw_price).quantize(Decimal("0.01"))
            if unit_price < 0:
                raise ValueError
        except (ValueError, TypeError, InvalidOperation, ArithmeticError):
            flash("La quantité et le prix unitaire doivent être valides.", "error")
            return render_template("animation_sale_edit.html", sale=sale)

        sale.quantity = quantity
        sale.unit_price = unit_price
        try:
            db.session.commit()
            flash("Vente d'animation modifiée avec succès. Le montant total a été recalculé.", "success")
            return redirect(url_for("animation_sales.my_history"))
        except Exception:
            db.session.rollback()
            flash("Impossible de modifier la vente d'animation.", "error")

    return render_template("animation_sale_edit.html", sale=sale)


@animation_sales_bp.route("/animateur/<int:user_id>")
@login_required
@roles_required("admin")
def animateur_history(user_id):
    from app.models import AnimationSale

    animateur = User.query.get_or_404(user_id)
    if animateur.role != "animateur":
        abort(404)
    sales = AnimationSale.query.filter_by(animateur_id=animateur.id).order_by(
        AnimationSale.animation_date.desc(), AnimationSale.id.desc()
    ).all()

    by_date = {}
    for sale in sales:
        by_date.setdefault(sale.animation_date, []).append(sale)
    days = [
        {"animation_date": date, "items": items,
         "animateurs": [animateur.username],
         "total_quantity": sum(i.quantity for i in items),
         "total_amount": sum((i.total_amount for i in items), Decimal("0.00"))}
        for date, items in by_date.items()
    ]
    general_total = sum((day["total_amount"] for day in days), Decimal("0.00"))
    general_quantity = sum(day["total_quantity"] for day in days)
    return render_template(
        "animation_sales_history.html",
        days=days,
        general_total=general_total,
        general_quantity=general_quantity,
        selected_month="",
        is_admin=True,
        animateur=animateur,
        current_user_id=current_user.id,
    )
