"""Regression tests for prospection zone normalization by region."""

from app.routes.dashboard import _normalize_prospection_location, _validate_location


def test_interior_region_overrides_dakar_zone():
    zone, region = _normalize_prospection_location("CENTRE VILLE", "THIES")
    assert zone == "HORS DAKAR"
    assert region == "THIES"
    assert _validate_location(zone, region, "Thiès centre", required=True) is None


def test_interior_region_fills_an_empty_zone():
    zone, region = _normalize_prospection_location("", "kaolack")
    assert zone == "HORS DAKAR"
    assert region == "KAOLACK"
    assert _validate_location(zone, region, "Kaolack", required=True) is None


def test_dakar_region_keeps_selected_dakar_zone():
    zone, region = _normalize_prospection_location("CENTRE VILLE", "DAKAR")
    assert zone == "CENTRE VILLE"
    assert region == "DAKAR"
    assert _validate_location(zone, region, "Plateau", required=True) is None


def test_dakar_region_does_not_accept_hors_dakar_zone():
    zone, region = _normalize_prospection_location("HORS DAKAR", "DAKAR")
    assert _validate_location(zone, region, "Dakar", required=True) is not None
