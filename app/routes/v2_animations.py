from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, send_file
from flask_login import login_required, current_user
from app.extensions import db
from app.models import AnimationSale, AnimationEvidence, User, DIVISION_SUPPLIERS, get_active_product_prices_for_division
from app.permissions import is_admin, division_matches, require_division, normalized_division, normalized_role
from app.utils import roles_required

v2_animations_bp = Blueprint("v2_animations", __name__, url_prefix="/v2/animations")

def _parse_positive_int(value):
    try: value = int(str(value or "").strip())
    except (TypeError, ValueError): raise ValueError("La quantité doit être un nombre entier positif.")
    if value <= 0: raise ValueError("La quantité doit être supérieure à 0.")
    return value

def _parse_date(value):
    try: return date.fromisoformat(value)
    except (TypeError, ValueError): raise ValueError("La date de l'animation est invalide.")

def _visible_animateurs():
    query = User.query.filter_by(role="animateur", is_active_account=True).order_by(User.username)
    if not is_admin(): query = query.filter(User.id == current_user.id)
    return query.all()

def _can_access_animation(animation):
    return is_admin() or (animation.animateur_id == current_user.id and division_matches(current_user, animation.project))

@v2_animations_bp.route("/", methods=["GET", "POST"])
@login_required
@roles_required("admin", "animateur")
def index():
    division = normalized_division(current_user)
    if request.method == "POST":
        if is_admin():
            flash("La saisie des ventes d'animation est réservée aux animateurs.", "warning")
            return redirect(url_for("v2_animations.index"))
        try:
            require_division(division)
            pharmacy_name = (request.form.get("pharmacy_name") or "").strip()
            animation_date = _parse_date(request.form.get("animation_date"))
            if not pharmacy_name: raise ValueError("Le nom de la pharmacie est obligatoire.")
            prices = get_active_product_prices_for_division(division)
            lines = []
            for i in range(5):
                product_name = (request.form.get(f"product_name_{i}") or "").strip()
                raw_qty = request.form.get(f"quantity_{i}")
                if product_name or (raw_qty or "").strip():
                    if not product_name: raise ValueError(f"Le produit de la ligne {i + 1} est obligatoire.")
                    quantity = _parse_positive_int(raw_qty)
                    if product_name not in prices: raise ValueError(f"Le produit « {product_name} » n'est pas actif dans votre division.")
                    lines.append((product_name, quantity, Decimal(str(prices[product_name] or 0))))
            if not lines: raise ValueError("Ajoutez au moins une ligne produit avec une quantité.")
            evidence = None
            upload = request.files.get("evidence")
            if upload and upload.filename:
                data = upload.read()
                if not data: raise ValueError("Le justificatif photo est vide.")
                if len(data) > 8 * 1024 * 1024: raise ValueError("Le justificatif photo ne doit pas dépasser 8 Mo.")
                evidence = AnimationEvidence(animateur_id=current_user.id, pharmacy_name=pharmacy_name, animation_date=animation_date, project=division, filename=upload.filename[:255], mime_type=(upload.mimetype or "application/octet-stream")[:100], file_data=data, file_size=len(data))
                db.session.add(evidence); db.session.flush()
            for product_name, quantity, unit_price in lines:
                db.session.add(AnimationSale(animateur_id=current_user.id, pharmacy_name=pharmacy_name, animation_date=animation_date, product_name=product_name, quantity=quantity, unit_price=unit_price, project=division, evidence_id=evidence.id if evidence else None))
            db.session.commit()
            flash(f"Animation enregistrée : {len(lines)} produit(s), CA {sum(q * p for _, q, p in lines):,.0f} FCFA.", "success")
        except (ValueError, InvalidOperation) as exc:
            db.session.rollback(); flash(str(exc), "error")
        except Exception:
            db.session.rollback(); flash("Impossible d'enregistrer les ventes de l'animation. Aucune donnée n'a été appliquée.", "error")
        return redirect(url_for("v2_animations.index"))

    selected_division = (request.args.get("division") or "all").strip().lower()
    selected_animateur = request.args.get("animateur_id", type=int)
    selected_start = request.args.get("date_start") or ""
    selected_end = request.args.get("date_end") or ""
    query = AnimationSale.query
    if not is_admin(): query = query.filter(AnimationSale.animateur_id == current_user.id, AnimationSale.project == division)
    elif selected_division in DIVISION_SUPPLIERS: query = query.filter(AnimationSale.project == selected_division)
    if selected_animateur: query = query.filter(AnimationSale.animateur_id == selected_animateur)
    if selected_start: query = query.filter(AnimationSale.animation_date >= _parse_date(selected_start))
    if selected_end: query = query.filter(AnimationSale.animation_date <= _parse_date(selected_end))
    sales = query.order_by(AnimationSale.animation_date.desc(), AnimationSale.id.desc()).limit(500).all()
    total_quantity = sum(s.quantity for s in sales)
    total_revenue = sum((s.total_amount for s in sales), Decimal("0.00"))
    pharmacies = len({s.pharmacy_name.strip().lower() for s in sales})
    animation_keys = {(s.animateur_id, s.pharmacy_name.strip().lower(), s.animation_date, s.project) for s in sales}
    return render_template("v2/animations.html", sales=sales, total_quantity=total_quantity, total_revenue=total_revenue, pharmacies=pharmacies, total_animations=len(animation_keys), animateurs=_visible_animateurs(), selected_division=selected_division, selected_animateur=selected_animateur, selected_start=selected_start, selected_end=selected_end, can_enter=normalized_role() == "animateur", product_prices=get_active_product_prices_for_division(division) if division in DIVISION_SUPPLIERS else {})

@v2_animations_bp.route("/<int:sale_id>/supprimer", methods=["POST"])
@login_required
@roles_required("admin", "animateur")
def delete_sale(sale_id):
    sale = AnimationSale.query.get_or_404(sale_id)
    if not _can_access_animation(sale): abort(403)
    evidence = sale.evidence
    try:
        db.session.delete(sale); db.session.flush()
        if evidence and not AnimationSale.query.filter_by(evidence_id=evidence.id).first(): db.session.delete(evidence)
        db.session.commit(); flash("Ligne d'animation supprimée.", "success")
    except Exception:
        db.session.rollback(); flash("Impossible de supprimer cette ligne d'animation.", "error")
    return redirect(url_for("v2_animations.index"))

@v2_animations_bp.route("/justificatif/<int:evidence_id>")
@login_required
@roles_required("admin", "animateur")
def evidence(evidence_id):
    item = AnimationEvidence.query.get_or_404(evidence_id)
    if not is_admin() and item.animateur_id != current_user.id: abort(403)
    return send_file(BytesIO(item.file_data), mimetype=item.mime_type, download_name=item.filename, as_attachment=False)
