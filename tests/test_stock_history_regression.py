def test_historical_stock_product_is_not_lost_when_catalog_is_empty(monkeypatch):
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
    monkeypatch.setattr(stock_routes, "request", type("Request", (), {"args": {}})())
    monkeypatch.setattr(stock_routes, "current_user", type("User", (), {"role": "commercial", "project": "nasmedic"})())

    assert stock_routes.available() == "ok"
    row = captured["groups"][0]["products"][0]
    assert row["product"] == "Produit archive"
    assert row["stocks"]["duopharm"]["quantity"] == 7
