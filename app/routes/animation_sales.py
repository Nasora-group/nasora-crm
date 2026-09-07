from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import User, get_active_products_for_division, get_active_product_prices_for_division
from app.utils import roles_required


animation_sales_bp = Blueprint("animation_sales", __name__, url_prefix="/animations/ventes")


@animation_sales_bp.route("/nouvelle", methods=["GET", "POST"])
@login_required
@roles_required("admin", "commercial")
def new_animation_sale():
    """Create an animation sale; animateurs use this flow, admins can test it."""
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
            return render_template("animation_sale_form.html", products=products, prices=prices, form_data=request.form)

        try:
            animation_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            flash("La date d'animation est invalide.", "error")
            return render_template("animation_sale_form.html", products=products, prices=prices, form_data=request.form)

        items = []
        for product_name in products:
            quantity = request.form.get(f"quantity__{product_name}", type=int)
            if quantity and quantity > 0:
                items.append((product_name, quantity, prices.get(product_name, 0)))

        if not items:
            flash("Sélectionnez au moins un produit et renseignez une quantité vendue.", "error")
            return render_template("animation_sale_form.html", products=products, prices=prices, form_data=request.form)

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

    return render_template("animation_sale_form.html", products=products, prices=prices, form_data={})


@animation_sales_bp.route("/historique")
@login_required
@roles_required("admin", "commercial")
def my_history():
    from app.models import AnimationSale

    query = AnimationSale.query
    if current_user.role != "admin":
        query = query.filter_by(project=(current_user.project or "").strip().lower())

    sales = query.order_by(AnimationSale.animation_date.desc(), AnimationSale.id.desc()).all()
    grouped = []
    groups = {}
    for sale in sales:
        key = (sale.animateur_id, sale.pharmacy_name, sale.animation_date)
        groups.setdefault(key, []).append(sale)
    for (animateur_id, pharmacy, animation_date), items in groups.items():
        grouped.append({
            "animateur": User.query.get(animateur_id),
            "pharmacy_name": pharmacy,
            "animation_date": animation_date,
            "items": items,
            "total_quantity": sum(i.quantity for i in items),
            "total_amount": sum((i.total_amount for i in items), 0),
        })

    return render_template("animation_sales_history.html", groups=grouped, is_admin=current_user.role == "admin")


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

    groups = {}
    for sale in sales:
        key = (sale.pharmacy_name, sale.animation_date)
        groups.setdefault(key, []).append(sale)
    history = [
        {"pharmacy_name": pharmacy, "animation_date": date, "items": items,
         "total_quantity": sum(i.quantity for i in items),
         "total_amount": sum((i.total_amount for i in items), 0)}
        for (pharmacy, date), items in groups.items()
    ]
    return render_template("animation_sales_history.html", groups=history, is_admin=True, animateur=animateur)
