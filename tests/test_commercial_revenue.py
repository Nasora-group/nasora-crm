def test_commercial_revenue_helpers_exist():
    from app.routes.vm_cockpit import _commercial_revenue, _commercial_revenue_detail
    assert callable(_commercial_revenue)
    assert callable(_commercial_revenue_detail)
