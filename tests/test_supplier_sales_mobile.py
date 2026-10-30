from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "app" / "routes" / "sales.py"
TEMPLATE = ROOT / "app" / "templates" / "supplier_sales.html"


def test_supplier_sales_form_defaults_to_today_on_get():
    content = ROUTE.read_text(encoding="utf-8")

    assert "if request.method == \"GET\" and form.sale_date.data is None:" in content
    assert "form.sale_date.data = date.today()" in content


def test_supplier_sales_form_has_mobile_product_cards_and_no_gradients():
    content = TEMPLATE.read_text(encoding="utf-8")

    assert 'data-label="Produit"' in content
    assert 'data-label="Prix HT"' in content
    assert 'data-label="Quantité vendue"' in content
    assert "@media(max-width:800px)" in content
    assert "sales-table tbody{display:grid" in content
    assert "linear-gradient" not in content


def test_animation_sale_styles_do_not_corrupt_document_title():
    template = ROOT / "app" / "templates" / "animation_sale_form.html"
    content = template.read_text(encoding="utf-8")

    assert content.count("{% block title %}") == 1
    title_block = content.split("{% block title %}", 1)[1].split("{% endblock %}", 1)[0]
    assert "<style>" not in title_block
    assert "Saisir les ventes d'animation" in title_block
    assert "{% block content %}" in content
    assert ".ns-animation-product" in content
