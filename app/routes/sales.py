import logging
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.forms import SupplierSalesForm
from app.models import SUPPLIERS
from app.utils import roles_required

logger = logging.getLogger(__name__)

sales_bp = Blueprint("sales", __name__)


def _handle_supplier_sales(slug, template_name):
    supplier = SUPPLIERS[slug]
    product_model = supplier["product_model"]
    sale_model = supplier["sale_model"]
    division = supplier["division"]

    # Un commercial ne peut saisir que les ventes de sa propre division.
    if current_user.role == "commercial" and current_user.project != division:
        flash("Accès non autorisé : cette rubrique ne concerne pas votre division.", "error")
        return redirect(url_for("dashboard.index"))

    form = SupplierSalesForm()
    products = product_model.query.order_by(product_model.name).all()
    read_only = current_user.role != "commercial"

    if request.method == "POST":
        if read_only:
            flash("Seuls les commerciaux peuvent saisir des ventes.", "error")
            return redirect(url_for(f"sales.{slug}"))

        if not form.validate_on_submit():
            flash("Merci de renseigner une date de saisie valide.", "error")
            return redirect(url_for(f"sales.{slug}"))

        sale_date = form.sale_date.data
        nb_ventes = 0

        try:
            for product in products:
                quantity = request.form.get(f"quantity_{product.id}", type=int)
                price = request.form.get(f"price_{product.id}", type=float)

                if quantity and quantity > 0:
                    sale = sale_model(
                        product_id=product.id,
                        quantity=quantity,
                        price=price if price is not None else product.default_price,
                        date=sale_date,
                        commercial_id=current_user.id,
                        project=division,
                    )
                    db.session.add(sale)
                    nb_ventes += 1

                # Mise à jour manuelle des niveaux de stock par grossiste (saisie inventaire)
                for wholesaler in ("duopharm", "ubipharm", "laborex", "sodipharm"):
                    field = f"stock_{wholesaler}_{product.id}"
                    value = request.form.get(field, type=int)
                    if value is not None:
                        setattr(product, f"stock_{wholesaler}", value)

            db.session.commit()
            if nb_ventes:
                flash(f"{nb_ventes} vente(s) {supplier['label']} enregistrée(s) avec succès.", "success")
            else:
                flash("Stocks mis à jour (aucune quantité vendue saisie).", "info")
        except Exception:
            db.session.rollback()
            logger.exception("Erreur lors de l'enregistrement des ventes %s", supplier["label"])
            flash("Erreur lors de l'enregistrement des ventes.", "error")

        return redirect(url_for(f"sales.{slug}"))

    return render_template(template_name, products=products, form=form, supplier=supplier, read_only=read_only)


@sales_bp.route("/nova_pharma_sales", methods=["GET", "POST"])
@login_required
@roles_required("admin", "commercial")
def nova_pharma():
    return _handle_supplier_sales("nova_pharma", "supplier_sales.html")


@sales_bp.route("/gilbert_sales", methods=["GET", "POST"])
@login_required
@roles_required("admin", "commercial")
def gilbert():
    return _handle_supplier_sales("gilbert", "supplier_sales.html")


@sales_bp.route("/eric_favre_sales", methods=["GET", "POST"])
@login_required
@roles_required("admin", "commercial")
def eric_favre():
    return _handle_supplier_sales("eric_favre", "supplier_sales.html")


@sales_bp.route("/trois_chene_sales", methods=["GET", "POST"])
@login_required
@roles_required("admin", "commercial")
def trois_chene():
    return _handle_supplier_sales("trois_chene", "supplier_sales.html")
