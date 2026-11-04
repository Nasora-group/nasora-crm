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
