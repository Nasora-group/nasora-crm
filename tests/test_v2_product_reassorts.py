def test_v2_reassorts_marks_urgent_and_low(monkeypatch):
    from app.routes import v2_products as routes

    rows = [
        {
            "division": "nasmedic",
            "laboratory": "Eric Favre",
            "product": "Produit rupture",
            "quantity": 20,
            "revenue": 100,
            "stocks": {"duopharm": 0, "sodipharm": 25},
            "ruptures": 1,
            "low_stocks": 0,
            "total_stock": 25,
        },
        {
            "division": "nasmedic",
            "laboratory": "Eric Favre",
            "product": "Produit faible",
            "quantity": 10,
            "revenue": 50,
            "stocks": {"duopharm": 7, "sodipharm": 20},
            "ruptures": 0,
            "low_stocks": 1,
            "total_stock": 27,
        },
        {
            "division": "nasmedic",
            "laboratory": "Eric Favre",
            "product": "Produit disponible",
            "quantity": 5,
            "revenue": 20,
            "stocks": {"duopharm": 20, "sodipharm": 30},
            "ruptures": 0,
            "low_stocks": 0,
            "total_stock": 50,
        },
    ]
    captured = {}
    monkeypatch.setattr(routes, "_catalog_rows", lambda division, month: rows)
    monkeypatch.setattr(
        routes,
        "render_template",
        lambda template, **context: captured.update(template=template, context=context) or "ok",
    )

    result = routes.reassorts.__wrapped__.__wrapped__()
    assert result == "ok"
    output = captured["context"]["rows"]
    assert [row["product"] for row in output] == ["Produit rupture", "Produit faible"]
    assert output[0]["priority"] == "Urgent"
    assert output[0]["affected_wholesalers"] == ["duopharm"]
    assert output[1]["priority"] == "À réapprovisionner"
    assert output[1]["affected_wholesalers"] == ["duopharm"]
