def test_stock_available_keeps_historical_products_visible(monkeypatch):
    from app import create_app
    from app.config import TestingConfig
    from app.routes import stock as stock_routes

    app = create_app(TestingConfig)
    app.config["LOGIN_DISABLED"] = True

    class Entry:
        division = "nasmedic"
        laboratory = "Ancien laboratoire"
        wholesaler = "duopharm"
        product_name = "Produit archive"
        quantity = 7

    monkeypatch.setattr(
        stock_routes,
        "_snapshot",
        lambda week_start: {
            ("nasmedic", "Ancien laboratoire", "duopharm", "Produit archive"): Entry()
        },
    )
    monkeypatch.setattr(stock_routes, "_catalog", lambda: [])
    monkeypatch.setattr(stock_routes, "_allowed_divisions", lambda: ("nasmedic",))
    captured = {}
    monkeypatch.setattr(
        stock_routes,
        "render_template",
        lambda template, **context: captured.update(context) or "ok",
    )
    monkeypatch.setattr(
        stock_routes,
        "current_user",
        type("User", (), {"role": "commercial", "project": "nasmedic"})(),
    )

    with app.test_request_context("/stock/disponible"):
        assert stock_routes.available() == "ok"
    row = captured["groups"][0]["products"][0]
    assert row["product"] == "Produit archive"
    assert row["stocks"]["duopharm"]["quantity"] == 7
