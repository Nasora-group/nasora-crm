import csv
import io
import logging
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

import pandas as pd
from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import SupplierSalesForm
from app.models import SUPPLIERS
from app.permissions import division_matches
from app.utils import roles_required

logger = logging.getLogger(__name__)
sales_import_bp = Blueprint("sales_import", __name__)

# The order and reference prices below are the user's requested import templates.
ERIC_FAVRE_CATALOG = [
    ("Chronoerect", "3.58"),
    ("Special Kid calcium", "3.00"),
    ("Special Kid Fer", "3.00"),
    ("Special Kid immunite", "3.00"),
    ("Special Kid multivit", "3.00"),
    ("Special Kid nez et gorge", "3.00"),
    ("Special Kid appetit nutri+", "3.00"),
    ("Special Kid probiotiques", "8.56"),
    ("Special Kid rehydratation", "3.00"),
    ("Special Kid sol spray nasal F/50ML", "3.00"),
    ("Special Kid sommeil", "3.00"),
    ("Special Kid Soulage doux", "3.00"),
    ("Special Kid Zinc", "3.00"),
    ("Special Kid Appetit duo 125ML", "3.00"),
    ("Special Kid CA MAG ZC VIT DC125ML", "3.00"),
    ("Time Sex Control", "6.90"),
    ("Appetit boost", "3.00"),
    ("Flexaren gel de massage 75ML", "6.00"),
    ("Flexaren gelule BT30", "4.00"),
    ("Carbo DTOX GELU", "3.00"),
    ("Bum Bum gel 200ML", "12.96"),
    ("Endol Roll on 50ML", "10.32"),
    ("Microbiozym", "6.61"),
    ("Pure Collagen", "15.73"),
    ("Artiroxyne Btes de 90", "13.50"),
    ("Artiroxyne Btes de 15", "3.89"),
]
TROIS_CHENES_CATALOG = [
    ("ASTHE 1000", "6.95"), ("BOIS BANDE", "3.50"), ("CARBOLINE", "2.05"),
    ("MYOCALM PATCH", "5.60"), ("DIARILIUM SOL BV UNICADOSE", "2.64"),
    ("DYSMECALM CPR B/15", "2.00"), ("EASY MOM GROSSESSE GEL B/30", "3.40"),
    ("EFIRUB CPR B/30", "3.70"), ("EFIRUB PDRE SOL BUV SACH B/8", "3.40"),
    ("FLATUPLEXIN", "5.45"), ("MYOCALM", "3.60"), ("MYOCALM CRAMP", "1.45"),
    ("OSTEOPHYTUM CP", "6.95"), ("OSTEOPHYTUM GEL 100ML", "4.30"),
    ("OSTEOPHYTUM PATCH/14", "2.55"), ("SEDABUCCIL", "3.60"),
    ("SOMNIPLEX MELATONINE CPR", "5.50"), ("VAGALINE SPRAY BUCCAL F/25ML", "3.95"),
    ("VAGALINE CPR B/15", "2.45"), ("SPRAY NASAL", "3.55"),
    ("MY CARE ROLL ON 50ML", "4.10"), ("MY CARE SPRAY 100ML", "4.40"),
    ("INFLAKIN/30", "8.60"), ("INFLAKIN/10", "4.60"),
    ("LYMPHAVEINE CPR B30", "3.70"), ("LYMPHAVEINE H CPR BT15", "2.55"),
]
CATALOGS = {"eric_favre": ERIC_FAVRE_CATALOG, "trois_chene": TROIS_CHENES_CATALOG}

# Names used in commercial templates may differ from the canonical CRM label.
# Keep aliases scoped to their supplier to avoid cross-laboratory matches.
PRODUCT_NAME_ALIASES = {
    "eric_favre": {
        "specialkidappetitnutri": "specialkidnutri",
    },
}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_IMPORT_ROWS = 1000


def _normalize(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _find_product_by_name(slug, by_name, label):
    """Resolve only exact or unambiguous close names among active supplier products."""
    normalized = _normalize(label)
    product = by_name.get(normalized)
    if product is not None:
        return product

    canonical_name = PRODUCT_NAME_ALIASES.get(slug, {}).get(normalized)
    if canonical_name:
        product = by_name.get(canonical_name)
        if product is not None:
            return product

    # Accept harmless suffix/prefix differences (e.g. pack size) only when
    # exactly one active product contains all meaningful label tokens.
    tokens = set(re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKD", str(label or "")).lower()))
    tokens = {token for token in tokens if token not in {"de", "du", "la", "le", "et"}}
    if not tokens:
        return None
    candidates = []
    for candidate_name, candidate in by_name.items():
        candidate_tokens = set(re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKD", str(candidate.name or "")).lower()))
        candidate_tokens = {token for token in candidate_tokens if token not in {"de", "du", "la", "le", "et"}}
        if tokens <= candidate_tokens or candidate_tokens <= tokens:
            candidates.append(candidate)
    return candidates[0] if len(candidates) == 1 else None


def _supplier_or_404(slug):
    supplier = SUPPLIERS.get(slug)
    if not supplier or supplier.get("archived"):
        abort(404)
    if not division_matches(current_user, supplier["division"]):
        abort(403)
    return supplier


def _template_rows(slug, products):
    by_name = {_normalize(product.name): product for product in products}
    catalog = CATALOGS.get(slug)
    if catalog is None:
        return [
            {
                "product_id": product.id,
                "reference": product.reference or "",
                "product": product.name,
                "price_ht": str(Decimal(str(product.default_price or "0.00")).quantize(Decimal("0.01"))),
                "quantity": "",
            }
            for product in products
        ]

    # Build templates from the supplier's active CRM catalog, never from
    # unmatched static labels. This prevents blank IDs and impossible imports.
    rows = []
    included_ids = set()
    for label, reference_price in catalog:
        product = _find_product_by_name(slug, by_name, label)
        if product is None or product.id in included_ids:
            continue
        included_ids.add(product.id)
        rows.append({
            "product_id": product.id,
            "reference": product.reference or "",
            "product": product.name,
            "price_ht": reference_price,
            "quantity": "",
        })

    # Include any other active supplier products not present in the commercial
    # reference list, so the template remains complete as the CRM evolves.
    for product in products:
        if product.id in included_ids:
            continue
        rows.append({
            "product_id": product.id,
            "reference": product.reference or "",
            "product": product.name,
            "price_ht": str(Decimal(str(product.default_price or "0.00")).quantize(Decimal("0.01"))),
            "quantity": "",
        })
    return rows


def _read_upload(upload):
    filename = (upload.filename or "").lower()
    raw = upload.read()
    if not raw:
        raise ValueError("Le fichier est vide.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("Le fichier dépasse la limite de 5 Mo.")
    try:
        if filename.endswith(".csv"):
            frame = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False, sep=None, engine="python", encoding="utf-8-sig")
        elif filename.endswith(".xlsx"):
            frame = pd.read_excel(io.BytesIO(raw), dtype=str, keep_default_na=False, engine="openpyxl")
        else:
            raise ValueError("Format non accepté. Utilise un fichier .xlsx ou .csv.")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Impossible de lire le fichier. Vérifie le modèle Excel ou CSV.") from exc

    if len(frame.index) > MAX_IMPORT_ROWS:
        raise ValueError(f"Le fichier dépasse {MAX_IMPORT_ROWS} lignes.")
    columns = {_normalize(column): column for column in frame.columns}
    aliases = {
        "product_id": ("productid", "idproduit"),
        "reference": ("reference", "ref"),
        "product": ("product", "produit", "nomproduit"),
        "price_ht": ("priceht", "prixht", "prixunitaire"),
        "quantity": ("quantity", "quantite", "quantitevendue", "qte"),
    }
    selected = {}
    for target, names in aliases.items():
        for name in names:
            if name in columns:
                selected[target] = columns[name]
                break
    if "product" not in selected and "product_id" not in selected and "reference" not in selected:
        raise ValueError("Colonne produit manquante. Utilise le modèle fourni.")
    if "quantity" not in selected:
        raise ValueError("Colonne quantité manquante. Utilise le modèle fourni.")

    records = []
    for row_number, (_, row) in enumerate(frame.iterrows(), start=2):
        records.append((row_number, {key: str(row[col]).strip() for key, col in selected.items()}))
    return records


def _validated_sales(slug, supplier, records):
    product_model = supplier["product_model"]
    products = product_model.query.filter_by(is_active=True).all()
    by_id = {str(product.id): product for product in products}
    by_reference = {_normalize(product.reference): product for product in products if product.reference}
    by_name = {_normalize(product.name): product for product in products}
    validated = []
    seen = set()

    for row_number, row in records:
        raw_quantity = row.get("quantity", "").strip()
        if not raw_quantity:
            continue
        try:
            quantity_decimal = Decimal(raw_quantity.replace(" ", "").replace(",", "."))
            if quantity_decimal != quantity_decimal.to_integral_value() or quantity_decimal < 0:
                raise InvalidOperation
            quantity = int(quantity_decimal)
        except (InvalidOperation, ValueError):
            raise ValueError(f"Ligne {row_number} : la quantité doit être un entier positif ou nul.")
        if quantity == 0:
            continue

        product = None
        if row.get("product_id"):
            product = by_id.get(row["product_id"])
        if product is None and row.get("reference"):
            product = by_reference.get(_normalize(row["reference"]))
        if product is None and row.get("product"):
            product = _find_product_by_name(slug, by_name, row["product"])
        if product is None:
            label = row.get("product") or row.get("reference") or row.get("product_id") or "non renseigné"
            raise ValueError(f"Ligne {row_number} : produit « {label} » introuvable ou inactif dans ce laboratoire.")
        if product.id in seen:
            raise ValueError(f"Ligne {row_number} : le produit « {product.name} » apparaît plusieurs fois.")
        seen.add(product.id)

        raw_price = row.get("price_ht", "").strip()
        if raw_price:
            try:
                price = Decimal(raw_price.replace(" ", "").replace(",", "."))
                if not price.is_finite() or price < 0:
                    raise InvalidOperation
                price = price.quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError):
                raise ValueError(f"Ligne {row_number} : prix HT invalide.")
        else:
            price = Decimal(str(product.default_price or "0.00")).quantize(Decimal("0.01"))
        validated.append((product, quantity, price))
    if not validated:
        raise ValueError("Aucune quantité vendue positive à importer.")
    return validated


@sales_import_bp.route("/sales/<slug>/import", methods=["GET", "POST"])
@login_required
@roles_required("admin", "commercial")
def import_sales(slug):
    supplier = _supplier_or_404(slug)
    form = SupplierSalesForm()
    if request.method == "GET" and form.sale_date.data is None:
        form.sale_date.data = date.today()

    if request.method == "POST":
        upload = request.files.get("sales_file")
        if not form.validate_on_submit():
            flash("Merci de renseigner une date de vente valide.", "error")
        elif upload is None or not upload.filename:
            flash("Sélectionne un fichier Excel (.xlsx) ou CSV (.csv).", "error")
        else:
            try:
                records = _read_upload(upload)
                validated = _validated_sales(slug, supplier, records)
                sale_date = form.sale_date.data
                sale_model = supplier["sale_model"]
                sales = [
                    sale_model(
                        product_id=product.id,
                        quantity=quantity,
                        price=price,
                        date=sale_date,
                        commercial_id=current_user.id,
                        project=supplier["division"],
                    )
                    for product, quantity, price in validated
                ]
                db.session.add_all(sales)
                db.session.commit()
                flash(f"Import réussi : {len(sales)} produit(s) enregistré(s) pour {supplier['label']}. Les stocks grossistes n'ont pas été modifiés.", "success")
                return redirect(url_for(f"sales.{slug}"))
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "error")
            except Exception:
                db.session.rollback()
                logger.exception("Échec import ventes %s", supplier["label"])
                flash("Import non enregistré. Vérifie le fichier ou contacte l'administrateur.", "error")

    return render_template("supplier_sales_import.html", supplier=supplier, slug=slug, form=form)


@sales_import_bp.route("/sales/<slug>/template.<format_name>")
@login_required
@roles_required("admin", "commercial")
def download_sales_template(slug, format_name):
    supplier = _supplier_or_404(slug)
    if format_name not in {"csv", "xlsx"}:
        abort(404)
    products = supplier["product_model"].query.filter_by(is_active=True).order_by(supplier["product_model"].name).all()
    rows = _template_rows(slug, products)
    columns = ["product_id", "reference", "product", "price_ht", "quantity"]
    frame = pd.DataFrame(rows, columns=columns)
    output = io.BytesIO()
    if format_name == "csv":
        text_buffer = io.StringIO()
        writer = csv.DictWriter(text_buffer, fieldnames=columns, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        output.write(("\ufeff" + text_buffer.getvalue()).encode("utf-8"))
        mimetype = "text/csv; charset=utf-8"
    else:
        frame.to_excel(output, index=False, engine="xlsxwriter")
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    output.seek(0)
    extension = "csv" if format_name == "csv" else "xlsx"
    return send_file(output, mimetype=mimetype, as_attachment=True, download_name=f"modele_ventes_{slug}.{extension}")
