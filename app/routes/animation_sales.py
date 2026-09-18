from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, send_file
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user

from app.extensions import db
from app.models import User, AnimationEvidence, get_active_products_for_division, get_active_product_prices_for_division
from app.utils import roles_required

animation_sales_bp = Blueprint("animation_sales", __name__, url_prefix="/animations/ventes")


def _render_sale_form(products, prices, form_data):
    return render_template("animation_sale_form.html", products=products, prices=prices, form_data=form_data)


def _parse_sale_date(raw):
    try:
        return datetime.strptime((raw or "").strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _parse_positive_quantity(raw):
    try:
        value = int((raw or "").strip())
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


def _parse_non_negative_price(raw):
    try:
        value = Decimal((raw or "").strip().replace(",", ".")).quantize(Decimal("0.01"))
        return value if value >= 0 else None
    except (InvalidOperation, TypeError, ValueError, ArithmeticError):
        return None


MAX_EVIDENCE_SIZE = 5 * 1024 * 1024
ALLOWED_EVIDENCE_TYPES = {
    "image/jpeg": (".jpg", ".jpeg"),
    "image/png": (".png",),
    "image/webp": (".webp",),
}


def _read_animation_evidence(file_storage):
    """Validate and read one pharmacy animation proof image into memory."""
    if not file_storage or not file_storage.filename:
        raise ValueError("Le justificatif photo de l'animation est obligatoire.")

    filename = secure_filename(file_storage.filename)
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime_type = (file_storage.mimetype or "").lower().strip()
    allowed_extensions = ALLOWED_EVIDENCE_TYPES.get(mime_type)
    if not allowed_extensions or extension not in allowed_extensions:
        raise ValueError("Le justificatif doit être une image JPG, PNG ou WEBP.")

    data = file_storage.read(MAX_EVIDENCE_SIZE + 1)
    if len(data) > MAX_EVIDENCE_SIZE:
        raise ValueError("Le justificatif ne doit pas dépasser 5 Mo.")

    valid_signature = (
        (mime_type == "image/jpeg" and data.startswith(b"\xff\xd8\xff"))
        or (mime_type == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n"))
        or (mime_type == "image/webp" and len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP")
    )
    if not valid_signature:
        raise ValueError("Le fichier envoyé ne correspond pas à une image JPG, PNG ou WEBP valide.")

    return {
        "filename": filename[:255] or "justificatif-animation",
        "mime_type": mime_type,
        "file_data": data,
        "file_size": len(data),
    }


@animation_sales_bp.route("/nouvelle", methods=["GET", "POST"])
@login_required
@roles_required("admin", "commercial", "animateur")
def new_animation_sale():
    """Create one or more animation-sale lines in FCFA."""
    if current_user.role not in {"animateur", "admin"}:
        abort(403)

    division = (current_user.project or "").strip().lower()
    products = get_active_products_for_division(division)
    prices = get_active_product_prices_for_division(division)

    if request.method == "POST":
        pharmacy = (request.form.get("pharmacy_name") or "").strip()
        raw_date = (request.form.get("animation_date") or "").strip()
        animation_date = _parse_sale_date(raw_date)
        if not pharmacy or len(pharmacy) > 200 or not animation_date:
            flash("Le nom de la pharmacie et une date d'animation valide sont obligatoires.", "error")
            return _render_sale_form(products, prices, request.form)

        items = []
        invalid_product = None
        allowed_products = set(products)
        for product_name in products:
            raw_quantity = request.form.get(f"quantity__{product_name}")
            raw_price = request.form.get(f"unit_price__{product_name}")
            if not (raw_quantity or raw_price):
                continue
            quantity = _parse_positive_quantity(raw_quantity)
            unit_price = _parse_non_negative_price(raw_price)
            if quantity is None or unit_price is None:
                invalid_product = product_name
                break
            items.append((product_name, quantity, unit_price))

        if invalid_product:
            flash(f"La quantité et le prix unitaire de « {invalid_product} » doivent être valides.", "error")
            return _render_sale_form(products, prices, request.form)
        if not items:
            flash("Sélectionnez au moins un produit et renseignez sa quantité et son prix unitaire.", "error")
            return _render_sale_form(products, prices, request.form)
        if any(product_name not in allowed_products for product_name, _, _ in items):
            flash("Un produit sélectionné n'est pas disponible dans cette division.", "error")
            return _render_sale_form(products, prices, request.form)

        try:
            evidence_data = _read_animation_evidence(request.files.get("animation_evidence"))
            evidence = AnimationEvidence(
                animateur_id=current_user.id,
                pharmacy_name=pharmacy,
                animation_date=animation_date,
                project=division,
                **evidence_data,
            )
            db.session.add(evidence)
            db.session.flush()

            from app.models import AnimationSale
            for product_name, quantity, unit_price in items:
                db.session.add(AnimationSale(
                    animateur_id=current_user.id,
                    pharmacy_name=pharmacy,
                    animation_date=animation_date,
                    product_name=product_name,
                    quantity=quantity,
                    unit_price=unit_price,
                    project=division,
                    evidence_id=evidence.id,
                ))
            db.session.commit()
            flash(f"Animation enregistrée : {len(items)} produit(s) vendu(s).", "success")
            return redirect(url_for("animation_sales.my_history"))
        except Exception:
            db.session.rollback()
            flash("Impossible d'enregistrer les ventes de l'animation. Aucun changement n'a été appliqué.", "error")
            return _render_sale_form(products, prices, request.form)

    return _render_sale_form(products, prices, {})


def _animation_sales_query():
    """Return animation sales restricted to the authenticated user's scope."""
    from app.models import AnimationSale
    query = AnimationSale.query
    if current_user.role == "animateur":
        query = query.filter_by(animateur_id=current_user.id)
    elif current_user.role != "admin":
        query = query.filter_by(project=(current_user.project or "").strip().lower())
    return query


def _group_sales(sales):
    by_date = {}
    for sale in sales:
        by_date.setdefault(sale.animation_date, []).append(sale)

    days = []
    for animation_date, items in by_date.items():
        by_pharmacy = {}
        for sale in items:
            by_pharmacy.setdefault(sale.pharmacy_name, []).append(sale)
        pharmacies = []
        for pharmacy_name, pharmacy_items in sorted(by_pharmacy.items(), key=lambda pair: pair[0].lower()):
            pharmacies.append({
                "pharmacy_name": pharmacy_name,
                "items": pharmacy_items,
                "total_quantity": sum(i.quantity for i in pharmacy_items),
                "total_amount": sum((i.total_amount for i in pharmacy_items), Decimal("0.00")),
                "animateurs": sorted({sale.animateur.username if sale.animateur else "-" for sale in pharmacy_items}),
                "evidence": next((sale.evidence for sale in pharmacy_items if sale.evidence), None),
            })
        days.append({
            "animation_date": animation_date,
            "pharmacies": pharmacies,
            "animateurs": sorted({sale.animateur.username if sale.animateur else "-" for sale in items}),
            "total_quantity": sum(i.quantity for i in items),
            "total_amount": sum((i.total_amount for i in items), Decimal("0.00")),
        })
    return days


@animation_sales_bp.route("/historique")
@login_required
@roles_required("admin", "commercial", "animateur")
def my_history():
    selected_month = (request.args.get("month") or "").strip()
    month_date = None
    if selected_month:
        try:
            month_date = datetime.strptime(selected_month, "%Y-%m").date()
        except ValueError:
            selected_month = ""

    pharmacy_filter = (request.args.get("pharmacy") or "").strip()
    selected_animator = (request.args.get("animateur_id") or "").strip()
    animator_id = None
    if selected_animator.isdigit():
        animator_id = int(selected_animator)

    query = _animation_sales_query()
    from app.models import AnimationSale
    if month_date:
        next_month = month_date.replace(year=month_date.year + 1, month=1, day=1) if month_date.month == 12 else month_date.replace(month=month_date.month + 1, day=1)
        query = query.filter(AnimationSale.animation_date >= month_date, AnimationSale.animation_date < next_month)
    if pharmacy_filter:
        query = query.filter(AnimationSale.pharmacy_name.ilike(f"%{pharmacy_filter}%"))
    if current_user.role == "admin" and animator_id:
        query = query.filter(AnimationSale.animateur_id == animator_id)

    sales = query.order_by(AnimationSale.animation_date.desc(), AnimationSale.pharmacy_name.asc(), AnimationSale.id.desc()).all()
    days = _group_sales(sales)
    general_total = sum((day["total_amount"] for day in days), Decimal("0.00"))
    general_quantity = sum(day["total_quantity"] for day in days)
    animators = User.query.filter_by(role="animateur").order_by(User.username.asc()).all() if current_user.role == "admin" else []
    pharmacies = sorted({row[0] for row in AnimationSale.query.with_entities(AnimationSale.pharmacy_name).distinct().all() if row[0]})
    return render_template("animation_sales_history.html", days=days, general_total=general_total, general_quantity=general_quantity, selected_month=selected_month, pharmacy_filter=pharmacy_filter, selected_animator=selected_animator, animators=animators, pharmacies=pharmacies, is_admin=current_user.role == "admin", current_user_id=current_user.id)


@animation_sales_bp.route("/<int:sale_id>/modifier", methods=["GET", "POST"])
@login_required
@roles_required("admin", "animateur")
def edit_animation_sale(sale_id):
    """Edit all mutable fields; animateur may edit only their own sale."""
    from app.models import AnimationSale
    sale = AnimationSale.query.get_or_404(sale_id)
    if current_user.role == "animateur" and sale.animateur_id != current_user.id:
        abort(403)
    if current_user.role not in {"animateur", "admin"}:
        abort(403)

    division = (sale.project or current_user.project or "").strip().lower()
    products = get_active_products_for_division(division)
    if sale.product_name not in products:
        products = sorted(set(products) | {sale.product_name})

    if request.method == "POST":
        pharmacy = (request.form.get("pharmacy_name") or "").strip()
        animation_date = _parse_sale_date(request.form.get("animation_date"))
        product_name = (request.form.get("product_name") or "").strip()
        quantity = _parse_positive_quantity(request.form.get("quantity"))
        unit_price = _parse_non_negative_price(request.form.get("unit_price"))
        if not pharmacy or len(pharmacy) > 200:
            flash("Le nom de la pharmacie est obligatoire.", "error")
        elif not animation_date:
            flash("La date d'animation est invalide.", "error")
        elif not product_name or product_name not in products:
            flash("Le produit sélectionné n'est pas valide.", "error")
        elif quantity is None or unit_price is None:
            flash("La quantité et le prix unitaire doivent être valides.", "error")
        else:
            try:
                uploaded_evidence = request.files.get("animation_evidence")
                if uploaded_evidence and uploaded_evidence.filename:
                    evidence_data = _read_animation_evidence(uploaded_evidence)
                    if sale.evidence is None:
                        sale.evidence = AnimationEvidence(
                            animateur_id=sale.animateur_id,
                            pharmacy_name=pharmacy,
                            animation_date=animation_date,
                            project=division,
                            **evidence_data,
                        )
                    else:
                        sale.evidence.pharmacy_name = pharmacy
                        sale.evidence.animation_date = animation_date
                        sale.evidence.project = division
                        for key, value in evidence_data.items():
                            setattr(sale.evidence, key, value)
                elif sale.evidence is not None:
                    sale.evidence.pharmacy_name = pharmacy
                    sale.evidence.animation_date = animation_date
                    sale.evidence.project = division

                sale.pharmacy_name = pharmacy
                sale.animation_date = animation_date
                sale.product_name = product_name
                sale.quantity = quantity
                sale.unit_price = unit_price
                sale.project = division
                db.session.commit()
                flash("Vente d'animation modifiée avec succès. Le montant total a été recalculé.", "success")
                return redirect(url_for("animation_sales.my_history"))
            except Exception:
                db.session.rollback()
                flash("Impossible de modifier la vente d'animation. Aucun changement n'a été appliqué.", "error")

    return render_template("animation_sale_edit.html", sale=sale, products=products)


@animation_sales_bp.route("/<int:sale_id>/supprimer", methods=["POST"])
@login_required
@roles_required("admin", "animateur")
def delete_animation_sale(sale_id):
    """Delete an animation sale; animateur may delete only their own sale."""
    from app.models import AnimationSale
    sale = AnimationSale.query.get_or_404(sale_id)
    if current_user.role == "animateur" and sale.animateur_id != current_user.id:
        abort(403)
    if current_user.role not in {"animateur", "admin"}:
        abort(403)
    try:
        sale_date, pharmacy, product = sale.animation_date, sale.pharmacy_name, sale.product_name
        evidence = sale.evidence
        db.session.delete(sale)
        db.session.flush()
        if evidence is not None:
            from app.models import AnimationSale
            remaining_sale = AnimationSale.query.filter(
                AnimationSale.evidence_id == evidence.id,
                AnimationSale.id != sale.id,
            ).first()
            if remaining_sale is None:
                db.session.delete(evidence)
        db.session.commit()
        flash(f"Vente supprimée : {product} - {pharmacy} ({sale_date.strftime('%d/%m/%Y')}).", "success")
    except Exception:
        db.session.rollback()
        flash("Impossible de supprimer la vente d'animation. Aucun changement n'a été appliqué.", "error")
    return redirect(url_for("animation_sales.my_history"))


@animation_sales_bp.route("/justificatif/<int:evidence_id>")
@login_required
@roles_required("admin", "animateur")
def animation_evidence(evidence_id):
    evidence = AnimationEvidence.query.get_or_404(evidence_id)
    if current_user.role == "animateur" and evidence.animateur_id != current_user.id:
        abort(403)
    download = request.args.get("download") == "1"
    return send_file(
        BytesIO(evidence.file_data),
        mimetype=evidence.mime_type,
        as_attachment=download,
        download_name=evidence.filename,
        max_age=0,
    )


@animation_sales_bp.route("/animateur/<int:user_id>")
@login_required
@roles_required("admin")
def animateur_history(user_id):
    from app.models import AnimationSale
    animateur = User.query.get_or_404(user_id)
    if animateur.role != "animateur":
        abort(404)
    sales = AnimationSale.query.filter_by(animateur_id=animateur.id).order_by(AnimationSale.animation_date.desc(), AnimationSale.pharmacy_name.asc(), AnimationSale.id.desc()).all()
    days = _group_sales(sales)
    general_total = sum((day["total_amount"] for day in days), Decimal("0.00"))
    general_quantity = sum(day["total_quantity"] for day in days)
    return render_template("animation_sales_history.html", days=days, general_total=general_total, general_quantity=general_quantity, selected_month="", is_admin=True, animateur=animateur, current_user_id=current_user.id)
