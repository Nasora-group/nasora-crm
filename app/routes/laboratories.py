import csv
import io
import logging
import re
import unicodedata
from decimal import Decimal, InvalidOperation

import pandas as pd
from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Laboratory, LaboratoryProduct, User
from app.utils import roles_required

logger = logging.getLogger(__name__)
laboratories_bp = Blueprint("laboratories", __name__, url_prefix="/admin/laboratoires")
ALLOWED_CURRENCIES = ("XOF", "XAF", "EUR", "USD", "GBP", "MAD", "GHS", "NGN")
MAX_LOGO_BYTES = 2 * 1024 * 1024
CATALOG_COLUMNS = ("reference", "name", "price_ht")


def _slugify(value):
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")[:70]


def _parse_price(value):
    raw = str(value if value is not None else "").strip().replace(" ", "").replace(",", ".")
    if not raw:
        raise ValueError("Prix HT manquant.")
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        raise ValueError("Prix HT invalide.")
    if not amount.is_finite() or amount < 0 or amount > Decimal("9999999999.99"):
        raise ValueError("Prix HT hors limites.")
    return amount.quantize(Decimal("0.01"))


def _get_lab_or_404(lab_id):
    return Laboratory.query.get_or_404(lab_id)


def _save_logo(lab):
    upload = request.files.get("logo")
    if not upload or not upload.filename:
        return
    mime = (upload.mimetype or "").lower()
    if mime not in ("image/png", "image/jpeg", "image/webp"):
        raise ValueError("Le logo doit être une image PNG, JPG ou WEBP.")
    data = upload.read(MAX_LOGO_BYTES + 1)
    if not data or len(data) > MAX_LOGO_BYTES:
        raise ValueError("Le logo est vide ou dépasse 2 Mo.")
    lab.logo_data = data
    lab.logo_mime_type = mime


def _read_catalog(upload):
    filename = (upload.filename or "").lower()
    if filename.endswith(".csv"):
        raw = upload.read()
        try:
            frame = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False, sep=None, engine="python", encoding="utf-8-sig")
        except UnicodeDecodeError:
            frame = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False, sep=None, engine="python", encoding="latin-1")
    elif filename.endswith(".xlsx"):
        frame = pd.read_excel(upload, dtype=str).fillna("")
    else:
        raise ValueError("Format non accepté. Utilisez un fichier CSV ou Excel (.xlsx).")
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    aliases = {"reference produit": "reference", "référence": "reference", "ref": "reference", "produit": "name", "nom": "name", "prix ht": "price_ht", "prix": "price_ht"}
    frame = frame.rename(columns={column: aliases.get(column, column) for column in frame.columns})
    if set(frame.columns) & {"quantity", "quantite", "quantité", "stock", "qty"}:
        raise ValueError("Le catalogue ne doit contenir aucune colonne de quantité ou de stock.")
    missing = [column for column in CATALOG_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError("Colonnes obligatoires manquantes : " + ", ".join(missing) + ". Le modèle ne contient aucune quantité.")
    if frame.empty:
        raise ValueError("Le fichier ne contient aucun produit.")
    rows = []
    seen_refs, seen_names = set(), set()
    errors = []
    for index, row in frame.iterrows():
        line = index + 2
        reference = str(row.get("reference", "")).strip() or None
        name = str(row.get("name", "")).strip()
        try:
            price = _parse_price(row.get("price_ht", ""))
            if not name:
                raise ValueError("Nom du produit manquant.")
            ref_key = reference.casefold() if reference else None
            name_key = name.casefold()
            if ref_key and ref_key in seen_refs:
                raise ValueError("Référence répétée dans le fichier.")
            if name_key in seen_names:
                raise ValueError("Nom de produit répété dans le fichier.")
            if ref_key:
                seen_refs.add(ref_key)
            seen_names.add(name_key)
            rows.append({"reference": reference, "name": name, "price_ht": price})
        except ValueError as exc:
            errors.append(f"Ligne {line} : {exc}")
    if errors:
        raise ValueError("Import annulé. " + " | ".join(errors[:12]))
    return rows


@laboratories_bp.route("/", methods=["GET"])
@login_required
@roles_required("admin")
def index():
    laboratories = Laboratory.query.order_by(Laboratory.is_active.desc(), Laboratory.name.asc()).all()
    return render_template("admin_laboratories.html", laboratories=laboratories)


@laboratories_bp.route("/nouveau", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        currency = request.form.get("currency", "XOF").upper()
        slug = _slugify(request.form.get("slug") or name)
        if not name or not slug:
            flash("Le nom du laboratoire est obligatoire.", "error")
            return render_template("admin_laboratory_form.html", laboratory=None, users=User.query.filter_by(is_active_account=True).order_by(User.username).all(), currencies=ALLOWED_CURRENCIES)
        if currency not in ALLOWED_CURRENCIES:
            flash("Devise non autorisée.", "error")
            return render_template("admin_laboratory_form.html", laboratory=None, users=User.query.filter_by(is_active_account=True).order_by(User.username).all(), currencies=ALLOWED_CURRENCIES)
        if Laboratory.query.filter_by(slug=slug).first():
            flash("Ce code laboratoire existe déjà. Choisissez un autre code.", "error")
            return render_template("admin_laboratory_form.html", laboratory=None, users=User.query.filter_by(is_active_account=True).order_by(User.username).all(), currencies=ALLOWED_CURRENCIES)
        lab = Laboratory(name=name, slug=slug, currency=currency)
        try:
            _apply_form(lab)
            db.session.add(lab)
            db.session.commit()
            flash("Laboratoire créé. Vous pouvez maintenant importer son catalogue.", "success")
            return redirect(url_for("laboratories.detail", lab_id=lab.id))
        except (ValueError, IntegrityError) as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else "Impossible de créer ce laboratoire : code déjà utilisé.", "error")
    return render_template("admin_laboratory_form.html", laboratory=None, users=User.query.filter_by(is_active_account=True).order_by(User.username).all(), currencies=ALLOWED_CURRENCIES)


def _apply_form(lab):
    lab.name = request.form.get("name", "").strip()
    lab.slug = _slugify(request.form.get("slug") or lab.name)
    lab.description = request.form.get("description", "").strip() or None
    lab.address = request.form.get("address", "").strip() or None
    lab.city = request.form.get("city", "").strip() or None
    lab.country = request.form.get("country", "").strip() or None
    lab.phone = request.form.get("phone", "").strip() or None
    lab.email = request.form.get("email", "").strip() or None
    lab.website = request.form.get("website", "").strip() or None
    lab.currency = request.form.get("currency", "XOF").upper()
    if lab.currency not in ALLOWED_CURRENCIES:
        raise ValueError("Devise non autorisée.")
    monthly = request.form.get("monthly_objective", "").strip()
    annual = request.form.get("annual_objective", "").strip()
    lab.monthly_objective = _parse_price(monthly) if monthly else None
    lab.annual_objective = _parse_price(annual) if annual else None
    lab.is_active = request.form.get("is_active") == "on"
    user_ids = {int(value) for value in request.form.getlist("staff_ids") if value.isdigit()}
    lab.staff = User.query.filter(User.id.in_(user_ids), User.is_active_account.is_(True)).all() if user_ids else []
    _save_logo(lab)


@laboratories_bp.route("/<int:lab_id>", methods=["GET"])
@login_required
@roles_required("admin")
def detail(lab_id):
    lab = _get_lab_or_404(lab_id)
    products = LaboratoryProduct.query.filter_by(laboratory_id=lab.id).order_by(LaboratoryProduct.is_active.desc(), LaboratoryProduct.name.asc()).all()
    return render_template("admin_laboratory_detail.html", laboratory=lab, products=products)


@laboratories_bp.route("/<int:lab_id>/modifier", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit(lab_id):
    lab = _get_lab_or_404(lab_id)
    if request.method == "POST":
        try:
            _apply_form(lab)
            db.session.commit()
            flash("Fiche laboratoire mise à jour.", "success")
            return redirect(url_for("laboratories.detail", lab_id=lab.id))
        except (ValueError, IntegrityError) as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else "Ce code laboratoire est déjà utilisé.", "error")
    return render_template("admin_laboratory_form.html", laboratory=lab, users=User.query.filter_by(is_active_account=True).order_by(User.username).all(), currencies=ALLOWED_CURRENCIES)


@laboratories_bp.route("/<int:lab_id>/logo")
@login_required
@roles_required("admin")
def logo(lab_id):
    lab = _get_lab_or_404(lab_id)
    if not lab.logo_data:
        abort(404)
    return send_file(io.BytesIO(lab.logo_data), mimetype=lab.logo_mime_type or "image/png", max_age=3600)


@laboratories_bp.route("/<int:lab_id>/produits/nouveau", methods=["POST"])
@login_required
@roles_required("admin")
def add_product(lab_id):
    lab = _get_lab_or_404(lab_id)
    name = request.form.get("name", "").strip()
    reference = request.form.get("reference", "").strip() or None
    try:
        price = _parse_price(request.form.get("price_ht", ""))
        if not name:
            raise ValueError("Le nom du produit est obligatoire.")
        product = LaboratoryProduct(laboratory_id=lab.id, name=name, reference=reference, price_ht=price)
        db.session.add(product)
        db.session.commit()
        flash("Produit ajouté au catalogue.", "success")
    except (ValueError, IntegrityError) as exc:
        db.session.rollback()
        flash(str(exc) if isinstance(exc, ValueError) else "Cette référence existe déjà dans ce laboratoire.", "error")
    return redirect(url_for("laboratories.detail", lab_id=lab.id))


@laboratories_bp.route("/<int:lab_id>/produits/<int:product_id>/modifier", methods=["POST"])
@login_required
@roles_required("admin")
def edit_product(lab_id, product_id):
    lab = _get_lab_or_404(lab_id)
    product = LaboratoryProduct.query.filter_by(id=product_id, laboratory_id=lab.id).first_or_404()
    try:
        name = request.form.get("name", "").strip()
        if not name:
            raise ValueError("Le nom du produit est obligatoire.")
        product.name = name
        product.reference = request.form.get("reference", "").strip() or None
        product.price_ht = _parse_price(request.form.get("price_ht", ""))
        product.is_active = request.form.get("is_active") == "on"
        db.session.commit()
        flash("Produit mis à jour.", "success")
    except (ValueError, IntegrityError) as exc:
        db.session.rollback()
        flash(str(exc) if isinstance(exc, ValueError) else "Cette référence existe déjà dans ce laboratoire.", "error")
    return redirect(url_for("laboratories.detail", lab_id=lab.id))


@laboratories_bp.route("/<int:lab_id>/produits/importer", methods=["POST"])
@login_required
@roles_required("admin")
def import_products(lab_id):
    lab = _get_lab_or_404(lab_id)
    upload = request.files.get("catalog_file")
    if not upload or not upload.filename:
        flash("Sélectionnez un fichier CSV ou Excel.", "error")
        return redirect(url_for("laboratories.detail", lab_id=lab.id))
    try:
        rows = _read_catalog(upload)
        inserted = updated = 0
        for row in rows:
            product = None
            if row["reference"]:
                product = LaboratoryProduct.query.filter_by(laboratory_id=lab.id, reference=row["reference"]).first()
            if product is None:
                product = LaboratoryProduct.query.filter(
                    LaboratoryProduct.laboratory_id == lab.id,
                    db.func.lower(LaboratoryProduct.name) == row["name"].lower(),
                ).first()
            if product:
                product.name = row["name"]
                product.reference = row["reference"]
                product.price_ht = row["price_ht"]
                product.is_active = True
                updated += 1
            else:
                db.session.add(LaboratoryProduct(laboratory_id=lab.id, **row))
                inserted += 1
        db.session.commit()
        flash(f"Import terminé : {inserted} produit(s) ajouté(s), {updated} mis à jour. Aucun stock ni historique de vente modifié.", "success")
    except Exception as exc:
        db.session.rollback()
        logger.exception("Échec import catalogue laboratoire %s par %s", lab.slug, current_user.username)
        flash(f"Import annulé : {exc}", "error")
    return redirect(url_for("laboratories.detail", lab_id=lab.id))



@laboratories_bp.route("/<int:lab_id>/produits/exporter/<format_name>")
@login_required
@roles_required("admin")
def export_products(lab_id, format_name):
    lab = _get_lab_or_404(lab_id)
    if format_name not in ("csv", "xlsx"):
        abort(404)
    products = LaboratoryProduct.query.filter_by(laboratory_id=lab.id).order_by(LaboratoryProduct.name.asc()).all()
    frame = pd.DataFrame([
        {"reference": product.reference or "", "name": product.name, "price_ht": str(product.price_ht)}
        for product in products
    ], columns=list(CATALOG_COLUMNS))
    output = io.BytesIO()
    if format_name == "csv":
        output.write(frame.to_csv(index=False).encode("utf-8-sig"))
        mimetype, extension = "text/csv", "csv"
    else:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False, sheet_name="Produits")
        mimetype, extension = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    output.seek(0)
    return send_file(output, mimetype=mimetype, as_attachment=True, download_name=f"catalogue_{lab.slug}.{extension}")


@laboratories_bp.route("/modele/<format_name>")
@login_required
@roles_required("admin")
def download_template(format_name):
    if format_name not in ("csv", "xlsx"):
        abort(404)
    frame = pd.DataFrame(columns=list(CATALOG_COLUMNS))
    output = io.BytesIO()
    if format_name == "csv":
        output.write(frame.to_csv(index=False).encode("utf-8-sig"))
        mimetype, filename = "text/csv", "modele_universel_laboratoires.csv"
    else:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False, sheet_name="Produits")
            guide = pd.DataFrame({"Consignes": ["Une ligne par produit.", "Colonnes obligatoires : reference, name, price_ht.", "Ne pas ajouter de quantité ou de stock.", "Le prix est exprimé dans la devise définie sur la fiche du laboratoire."]})
            guide.to_excel(writer, index=False, sheet_name="Consignes")
        mimetype, filename = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "modele_universel_laboratoires.xlsx"
    output.seek(0)
    return send_file(output, mimetype=mimetype, as_attachment=True, download_name=filename)
