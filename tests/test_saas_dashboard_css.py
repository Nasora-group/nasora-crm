from pathlib import Path


def test_saas_dashboard_css_exists_and_contains_core_tokens():
    css = Path("app/static/css/nasora-saas-dashboard.css").read_text(encoding="utf-8")
    assert "--ns-green" in css
    assert ".kpi-card" in css
    assert ".responsive-table" in css
    assert "prefers-reduced-motion" in css
