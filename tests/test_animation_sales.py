from decimal import Decimal

from app.routes.animation_sales import _collect_animation_sale_items


def test_blank_quantity_ignores_prefilled_default_price():
    products = ["Produit vendu", "Produit non vendu"]
    form_data = {
        "quantity__Produit vendu": "2",
        "unit_price__Produit vendu": "5000",
        "quantity__Produit non vendu": "",
        "unit_price__Produit non vendu": "12000",
    }

    items, invalid_product = _collect_animation_sale_items(products, form_data)

    assert items == [("Produit vendu", 2, Decimal("5000.00"))]
    assert invalid_product is None


def test_quantity_requires_a_valid_price():
    products = ["Produit A"]
    form_data = {
        "quantity__Produit A": "2",
        "unit_price__Produit A": "",
    }

    items, invalid_product = _collect_animation_sale_items(products, form_data)

    assert items == []
    assert invalid_product == "Produit A"


def test_zero_quantity_is_ignored():
    products = ["Produit A"]
    form_data = {
        "quantity__Produit A": "0",
        "unit_price__Produit A": "5000",
    }

    items, invalid_product = _collect_animation_sale_items(products, form_data)

    assert items == []
    assert invalid_product is None


def test_animation_sales_csv_export_is_spreadsheet_friendly_and_complete():
    from datetime import date
    from types import SimpleNamespace

    from app.routes.animation_sales import _build_animation_sales_csv

    sale = SimpleNamespace(
        animation_date=date(2026, 11, 16),
        project="nasmedic",
        animateur=SimpleNamespace(username="Animatrice Test"),
        pharmacy_name="Pharmacie Centrale",
        product_name="Produit Test",
        unit_price=Decimal("2500.00"),
        quantity=3,
        total_amount=Decimal("7500.00"),
        evidence_id=12,
    )

    content = _build_animation_sales_csv([sale])

    assert content.startswith(chr(65279))
    assert "Date;Division;Animatrice;Pharmacie;Produit" in content
    assert "16/11/2026;nasmedic;Animatrice Test;Pharmacie Centrale;Produit Test" in content
    assert "2500.00;3;7500.00;Oui" in content


def test_animation_sales_csv_export_handles_empty_history():
    from app.routes.animation_sales import _build_animation_sales_csv

    content = _build_animation_sales_csv([])

    assert content.startswith(chr(65279))
    assert "Date;Division;Animatrice;Pharmacie;Produit" in content
    assert content.count(chr(10)) == 1
