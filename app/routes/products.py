import logging

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.forms import ProductForm, CSRFOnlyForm
from app.models import SUPPLIERS
from app.utils import roles_required

logger = logging.getLogger(__name__)

products_bp = Blueprint("products", __name__, url_prefix="/admin/produits")


def _get_supplier_or_404(slug):
    supplier = SUPPLIERS.get(slug)
    if not supplier:
        abort(404)
    return supplier


def _active_suppliers():
    """Fournisseurs non archivés, pour les onglets de navigation."""
    return {slug: s for slug, s in SUPPLIERS.items() if not s.get("archived")}


@products_bp.route("/<slug>")
@login_required
@roles_required("admin")
def list_products(slug):
    supplier = _get_supplier_or_404(slug)
    if supplier.get("archived"):
        flash(f"{supplier['label']} ne fait plus partie du groupe NASORA.", "error")
        return redirect(url_for("admin.dashboard"))
    product_model = supplier["product_model"]
    products = product_model.query.order_by(product_model.is_active.desc(), product_model.name).all()
    toggle_form = CSRFOnlyForm()
    return render_template(
        "admin_products.html",
        products=products,
        supplier=supplier,
        slug=slug,
        suppliers=_active_suppliers(),
        toggle_form=toggle_form,
    )


@products_bp.route("/<slug>/nouveau", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_product(slug):
    supplier = _get_supplier_or_404(slug)
    if supplier.get("archived"):
        flash(f"{supplier['label']} ne fait plus partie du groupe NASORA.", "error")
        return redirect(url_for("admin.dashboard"))
    product_model = supplier["product_model"]
    form = ProductForm()

    if form.validate_on_submit():
        try:
            product = product_model(
                name=form.name.data.strip(),
                reference=form.reference.data.strip() if form.reference.data else None,
                default_price=form.default_price.data,
                is_active=form.is_active.data,
            )
            db.session.add(product)
            db.session.commit()
            flash(f"Référence « {product.name} » ajoutée à {supplier['label']}.", "success")
            logger.info("Produit créé par %s : %s (%s)", current_user.username, product.name, slug)
            return redirect(url_for("products.list_products", slug=slug))
        except Exception:
            db.session.rollback()
            logger.exception("Erreur lors de la création du produit")
            flash("Erreur lors de la création de la référence.", "error")

    return render_template("admin_product_form.html", form=form, mode="create", supplier=supplier, slug=slug, product=None)


@products_bp.route("/<slug>/<int:product_id>/modifier", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_product(slug, product_id):
    supplier = _get_supplier_or_404(slug)
    product_model = supplier["product_model"]
    product = product_model.query.get_or_404(product_id)
    form = ProductForm(obj=product)

    if form.validate_on_submit():
        try:
            product.name = form.name.data.strip()
            product.reference = form.reference.data.strip() if form.reference.data else None
            product.default_price = form.default_price.data
            product.is_active = form.is_active.data
            db.session.commit()
            flash(f"Référence « {product.name} » mise à jour.", "success")
            logger.info("Produit modifié par %s : %s (%s)", current_user.username, product.name, slug)
            return redirect(url_for("products.list_products", slug=slug))
        except Exception:
            db.session.rollback()
            logger.exception("Erreur lors de la modification du produit")
            flash("Erreur lors de la mise à jour de la référence.", "error")

    return render_template("admin_product_form.html", form=form, mode="edit", supplier=supplier, slug=slug, product=product)


@products_bp.route("/<slug>/<int:product_id>/basculer-statut", methods=["POST"])
@login_required
@roles_required("admin")
def toggle_product(slug, product_id):
    supplier = _get_supplier_or_404(slug)
    product_model = supplier["product_model"]

    form = CSRFOnlyForm()
    if not form.validate_on_submit():
        flash("Requête invalide.", "error")
        return redirect(url_for("products.list_products", slug=slug))

    product = product_model.query.get_or_404(product_id)
    product.is_active = not product.is_active
    db.session.commit()
    etat = "activée" if product.is_active else "désactivée"
    flash(f"Référence « {product.name} » {etat}.", "success")
    return redirect(url_for("products.list_products", slug=slug))
