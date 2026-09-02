from datetime import date


def test_stock_available_keeps_historical_products_visible(monkeypatch):
    """A historical stock must remain visible if its product is no longer active."""
    from app.routes import stock as stock_routes

    class Entry:
        division = "nasmedic"
        laboratory = "Ancien laboratoire"
        wholesaler = "duopharm"
        product_name = "Produit archive"
        quantity = 7

    monkeypatch.setattr(stock_routes, "_snapshot", lambda week_start: {
        ("nasmedic", "Ancien laboratoire", "duopharm", "Produit archive"): Entry()
    })
    monkeypatch.setattr(stock_routes, "_catalog", lambda: [])
    monkeypatch.setattr(stock_routes, "_allowed_divisions", lambda: ("nasmedic",))

    captured = {}
    monkeypatch.setattr(stock_routes, "render_template", lambda template, **context: captured.update(context) or "ok")

    class Request:
        args = {}

    monkeypatch.setattr(stock_routes, "request", Request())
    monkeypatch.setattr(stock_routes, "current_user", type("User", (), {"role": "commercial", "project": "nasmedic"})())

    result = stock_routes.available()

    assert result == "ok"
    assert captured["groups"][0]["products"][0]["product"] == "Produit archive"
    assert captured["groups"][0]["products"][0]["stocks"]["duopharm"]["quantity"] == 7
