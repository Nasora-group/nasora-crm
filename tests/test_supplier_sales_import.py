from io import BytesIO
from types import SimpleNamespace

import pandas as pd
import pytest

from app.routes.sales_import import (
    ERIC_FAVRE_CATALOG,
    TROIS_CHENES_CATALOG,
    _normalize,
    _read_upload,
    _template_rows,
    _validated_sales,
)


class FakeQuery:
    def __init__(self, products):
        self.products = products

    def filter_by(self, **kwargs):
        return self

    def all(self):
        return self.products


def test_reference_catalogs_keep_requested_order_and_prices():
    assert ERIC_FAVRE_CATALOG[0] == ("Chronoerect", "3.58")
    assert ERIC_FAVRE_CATALOG[-1] == ("Artiroxyne Btes de 15", "3.89")
    assert TROIS_CHENES_CATALOG[0] == ("ASTHE 1000", "6.95")
    assert TROIS_CHENES_CATALOG[-1] == ("LYMPHAVEINE H CPR BT15", "2.55")


def test_template_rows_for_gilbert_use_active_database_products_and_prices():
    products = [
        SimpleNamespace(id=9, name="Produit Z", reference="REF-Z", default_price=4.25),
        SimpleNamespace(id=2, name="Produit A", reference=None, default_price=3.10),
    ]
    rows = _template_rows("gilbert", products)
    assert [row["product"] for row in rows] == ["Produit Z", "Produit A"]
    assert [row["price_ht"] for row in rows] == ["4.25", "3.10"]
    assert rows[1]["reference"] == ""


def test_fixed_catalog_template_keeps_chronology_and_matches_product_ids():
    product = SimpleNamespace(id=12, name="Chronoerect", reference="CHR", default_price=0)
    rows = _template_rows("eric_favre", [product])
    assert rows[0] == {
        "product_id": 12,
        "reference": "CHR",
        "product": "Chronoerect",
        "price_ht": "3.58",
        "quantity": "",
    }
    assert [(row["product"], row["price_ht"]) for row in rows] == ERIC_FAVRE_CATALOG
    assert len(rows) == 26


def test_eric_favre_template_keeps_all_26_labels_even_when_crm_products_are_missing():
    rows = _template_rows("eric_favre", [])
    assert [(row["product"], row["price_ht"]) for row in rows] == ERIC_FAVRE_CATALOG
    assert len(rows) == 26
    assert all(row["product_id"] == "" for row in rows)


def test_csv_upload_reads_french_semicolon_template():
    upload = SimpleNamespace(
        filename="ventes.csv",
        read=lambda: b"product_id;reference;product;price_ht;quantity\n1;REF1;Produit A;2,50;4\n",
    )
    records = _read_upload(upload)
    assert records == [(2, {
        "product_id": "1",
        "reference": "REF1",
        "product": "Produit A",
        "price_ht": "2,50",
        "quantity": "4",
    })]


def test_excel_upload_is_supported():
    buffer = BytesIO()
    pd.DataFrame([{
        "product_id": 1,
        "reference": "REF1",
        "product": "Produit A",
        "price_ht": 2.5,
        "quantity": 4,
    }]).to_excel(buffer, index=False, engine="xlsxwriter")
    payload = buffer.getvalue()
    upload = SimpleNamespace(filename="ventes.xlsx", read=lambda: payload)
    records = _read_upload(upload)
    assert records[0][1]["product"] == "Produit A"
    assert records[0][1]["quantity"] == "4"


def test_import_validates_all_sales_and_uses_default_price_when_blank():
    product = SimpleNamespace(id=1, name="Produit A", reference="REF1", default_price="5.20")
    model = SimpleNamespace(query=FakeQuery([product]))
    rows = [
        (2, {"product": "Produit A", "quantity": "3", "price_ht": ""}),
        (3, {"product": "Produit A", "quantity": "0", "price_ht": ""}),
    ]
    sales = _validated_sales("gilbert", {"product_model": model}, rows)
    assert len(sales) == 1
    assert sales[0][0] is product
    assert sales[0][1] == 3
    assert str(sales[0][2]) == "5.20"


def test_import_rejects_unknown_products_and_duplicate_rows():
    product = SimpleNamespace(id=1, name="Produit A", reference="REF1", default_price="5.20")
    model = SimpleNamespace(query=FakeQuery([product]))
    with pytest.raises(ValueError, match="introuvable"):
        _validated_sales("gilbert", {"product_model": model}, [
            (2, {"product": "Produit inconnu", "quantity": "1"})
        ])
    with pytest.raises(ValueError, match="plusieurs fois"):
        _validated_sales("gilbert", {"product_model": model}, [
            (2, {"product": "Produit A", "quantity": "1"}),
            (3, {"product": "Produit A", "quantity": "2"}),
        ])


def test_product_normalization_ignores_accents_and_spacing():
    assert _normalize("Spécial Kid - Calcium") == _normalize("special kid calcium")


def test_eric_favre_template_maps_commercial_nutri_label_to_active_crm_product():
    product = SimpleNamespace(
        id=7, name="Special kid nutri+", reference=None, default_price="3.00"
    )
    rows = _template_rows("eric_favre", [product])
    nutri_row = next(row for row in rows if row["product_id"] == 7)
    assert nutri_row["product"] == "Special Kid appetit nutri+"
    assert nutri_row["price_ht"] == "3.00"


def test_eric_favre_import_accepts_legacy_commercial_nutri_label():
    product = SimpleNamespace(
        id=7, name="Special kid nutri+", reference=None, default_price="3.00"
    )
    model = SimpleNamespace(query=FakeQuery([product]))
    sales = _validated_sales(
        "eric_favre",
        {"product_model": model},
        [(8, {
            "product": "Special Kid appetit nutri+",
            "quantity": "12",
            "price_ht": "3.00",
        })],
    )
    assert len(sales) == 1
    assert sales[0][0] is product
    assert sales[0][1] == 12
    assert str(sales[0][2]) == "3.00"


def test_fixed_catalog_template_preserves_exact_list_and_maps_available_products():
    products = [
        SimpleNamespace(id=21, name="Appetit Boost sirop", reference="AB", default_price="3.00"),
        SimpleNamespace(id=22, name="Special kid nutri+", reference="SKN", default_price="3.00"),
    ]
    rows = _template_rows("eric_favre", products)
    assert [(row["product"], row["price_ht"]) for row in rows] == ERIC_FAVRE_CATALOG
    assert len(rows) == 26
    assert next(row for row in rows if row["product_id"] == 22)["product"] == "Special Kid appetit nutri+"
    assert next(row for row in rows if row["product_id"] == 21)["product"] == "Appetit boost"
    assert next(row for row in rows if row["product"] == "Appetit boost")["price_ht"] == "3.00"


def test_eric_favre_appetit_boost_maps_to_live_catalog_product_name():
    product = SimpleNamespace(
        id=15, name="Apti boost Gel B30", reference=None, default_price="3.00"
    )
    model = SimpleNamespace(query=FakeQuery([product]))
    rows = _template_rows("eric_favre", [product])
    boost_row = next(row for row in rows if row["product"] == "Appetit boost")
    assert boost_row["product_id"] == 15
    sales = _validated_sales(
        "eric_favre",
        {"product_model": model},
        [(18, {
            "product": "Appetit boost",
            "quantity": "4",
            "price_ht": "3.00",
        })],
    )
    assert len(sales) == 1
    assert sales[0][0] is product
    assert sales[0][1] == 4


def test_eric_favre_artiroxyne_90_maps_to_live_artiroxine_product():
    artiroxine = SimpleNamespace(
        id=22, name="Artiroxine", reference=None, default_price="13.50"
    )
    artiroxyne_15 = SimpleNamespace(
        id=25, name="Artiroxyne Btes de 15", reference=None, default_price="3.89"
    )
    model = SimpleNamespace(query=FakeQuery([artiroxine, artiroxyne_15]))
    rows = _template_rows("eric_favre", [artiroxine, artiroxyne_15])
    row_90 = next(row for row in rows if row["product"] == "Artiroxyne Btes de 90")
    assert row_90["product_id"] == 22
    sales = _validated_sales(
        "eric_favre",
        {"product_model": model},
        [(26, {
            "product": "Artiroxyne Btes de 90",
            "quantity": "6",
            "price_ht": "13.50",
        })],
    )
    assert len(sales) == 1
    assert sales[0][0] is artiroxine
    assert sales[0][1] == 6
    assert str(sales[0][2]) == "13.50"


def test_import_matches_unique_product_name_with_packaging_suffix():
    product = SimpleNamespace(id=21, name="Appetit Boost sirop", reference="AB", default_price="3.00")
    model = SimpleNamespace(query=FakeQuery([product]))
    sales = _validated_sales(
        "eric_favre",
        {"product_model": model},
        [(18, {"product": "Appetit boost", "quantity": "4", "price_ht": "3.00"})],
    )
    assert len(sales) == 1
    assert sales[0][0] is product
