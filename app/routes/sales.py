import logging
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.forms import SupplierSalesForm, SaleEditForm, CSRFOnlyForm
from app.models import SUPPLIERS
from app.permissions import division_matches
from app.utils import roles_required

logger = logging.getLogger(__name__)
sales_bp = Blueprint("sales", __name__)


def _get_active_supplier_or_404(slug):
    supplier = SUPPLIERS.get(slug)
    if not supplier or supplier.get("archived"):
        abort(404)
    return supplier


def _parse_non_negative_int(raw_value):
    if raw_value is None or str(raw_value).strip() == "":
        return None
    try:
        value = int(str(raw_value).strip())
    except (TypeError, ValueError):
        raise ValueError("La quantité doit être un nombre entier.")
    if value < 0:
        raise ValueError("La quantité ne peut pas être négative.")
    return value


def _parse_non_negative_price(raw_value):
    if raw_value is None or str(raw_value).strip() == "":
        return None
    try:
        value = Decimal(str(raw_value).strip().replace(" ", "").replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Le prix doit être un nombre valide.")
    if value < 0:
        raise ValueError("Le prix ne peut pas être négatif.")
    return value


def _handle_supplier_sales(slug, template_name):
    supplier = _get_active_supplier_or_404(slug)
    product_model = supplier["product_model"]
    sale_model = supplier["sale_model"]
    division = supplier["division"]

    if not division_matches(current_user, division):
        abort(403)

    form = SupplierSalesForm()
    products = product_model.query.filter_by(is_active=True).order_by(product_model.name).all()
    read_only = False

    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Merci de renseigner une date de saisie valide.", "error")
            return render_template(template_name, products=products, form=form, supplier=supplier, read_only=False, slug=slug)

        sale_date = form.sale_date.data
        nb_ventes = 0
        try:
            for product in products:
                quantity = _parse_non_negative_int(request.form.get(f"quantity_{product.id}"))
                price = _parse_non_negative_price(request.form.get(f"price_{product.id}"))
                if quantity is not None and quantity > 0:
                    db.session.add(sale_model(
                        product_id=product.id,
                        quantity=quantity,
                        price=price if price is not None else product.default_price,
                        date=sale_date,
                        commercial_id=current_user.id,
                        project=division,
                    ))
                    nb_ventes += 1

                for wholesaler in ("duopharm", "ubipharm", "laborex", "sodipharm"):
                    value = _parse_non_negative_int(request.form.get(f"stock_{wholesaler}_{product.id}"))
                    if value is not None:
                        setattr(product, f"stock_{wholesaler}", value)

            db.session.commit()
            flash(
                f"{nb_ventes} vente(s) {supplier['label']} enregistrée(s) avec succès."
                if nb_ventes else "Stocks mis à jour (aucune quantité vendue saisie).",
                "success" if nb_ventes else "info",
            )
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
        except Exception:
            db.session.rollback()
            logger.exception("Erreur lors de l'enregistrement des ventes %s", supplier["label"])
            flash("Erreur lors de l'enregistrement des ventes. Aucune donnée partiellement enregistrée.", "error")
        return redirect(url_for(f"sales.{slug}"))

    return render_template(template_name, products=products, form=form, supplier=supplier, read_only=read_only, slug=slug)


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


@sales_bp.route("/admin/ventes/<slug>")
@login_required
@roles_required("admin")
def sales_history(slug):
    supplier = _get_active_supplier_or_404(slug)
    sale_model = supplier["sale_model"]
    product_model = supplier["product_model"]
    query = sale_model.query.join(product_model, sale_model.product_id == product_model.id)
    all_dates = [row[0] for row in db.session.query(sale_model.date).all()]
    available_months = sorted({d.strftime("%Y-%m") for d in all_dates if d}, reverse=True)
    selected_month = request.args.get("month", "")
    sales = query.order_by(sale_model.date.desc(), sale_model.id.desc()).all()
    if selected_month:
        sales = [s for s in sales if s.date and s.date.strftime("%Y-%m") == selected_month]
    page = max(1, request.args.get("page", 1, type=int) or 1)
    per_page = 25
    total = len(sales)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    page_items = sales[(page - 1) * per_page:page * per_page]
    total_amount = sum((Decimal(str(s.quantity or 0)) * Decimal(str(s.price or 0)) for s in sales), Decimal("0.00"))
    return render_template("admin_sales_history.html", supplier=supplier, slug=slug, sales=page_items, available_months=available_months, selected_month=selected_month, page=page, total_pages=total_pages, total_amount=total_amount, total_count=total, delete_form=CSRFOnlyForm(), suppliers=SUPPLIERS)


@sales_bp.route("/admin/ventes/<slug>/<int:sale_id>/modifier", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_sale(slug, sale_id):
    supplier = _get_active_supplier_or_404(slug)
    sale = supplier["sale_model"].query.get_or_404(sale_id)
    form = SaleEditForm(obj=sale)
    if form.validate_on_submit():
        try:
            sale.date = form.date.data
            sale.quantity = form.quantity.data
            sale.price = form.price.data
            db.session.commit()
            flash(f"Vente « {sale.product.name} » du {sale.date.strftime('%d/%m/%Y')} mise à jour.", "success")
            return redirect(url_for("sales.sales_history", slug=slug))
        except Exception:
            db.session.rollback()
            logger.exception("Erreur lors de la modification de la vente #%s", sale_id)
            flash("Erreur lors de la mise à jour de la vente.", "error")
    return render_template("admin_sale_form.html", form=form, supplier=supplier, slug=slug, sale=sale)


@sales_bp.route("/admin/ventes/<slug>/<int:sale_id>/supprimer", methods=["POST"])
@login_required
@roles_required("admin")
def delete_sale(slug, sale_id):
    supplier = _get_active_supplier_or_404(slug)
    sale = supplier["sale_model"].query.get_or_404(sale_id)
    form = CSRFOnlyForm()
    if not form.validate_on_submit():
        flash("Requête invalide.", "error")
        return redirect(url_for("sales.sales_history", slug=slug))
    product_name = sale.product.name
    sale_date = sale.date.strftime("%d/%m/%Y")
    db.session.delete(sale)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Erreur lors de la suppression de la vente #%s", sale_id)
        flash("Erreur lors de la suppression de la vente.", "error")
        return redirect(url_for("sales.sales_history", slug=slug))
    flash(f"Vente « {product_name} » du {sale_date} supprimée.", "success")
    return redirect(url_for("sales.sales_history", slug=slug))
