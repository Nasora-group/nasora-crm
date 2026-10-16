from pathlib import Path


def test_forge_inspired_visual_layer_is_loaded_without_changing_navigation_routes():
    base = Path("app/templates/base.html").read_text(encoding="utf-8")
    css = Path("app/static/css/forge-inspired-layout.css").read_text(encoding="utf-8")

    assert "forge-inspired-layout.css" in base
    assert ".nasora-sidebar" in css
    assert ".nasora-top-search" in css
    assert "#main-content.container" in css
    assert "@media(max-width:1023px)" in css
    assert "prefers-reduced-motion" in css

    # Keep the existing role-specific navigation and session controls intact.
    assert "url_for('admin.dashboard')" in base
    assert "url_for('planning.visualiser')" in base
    assert "url_for('clients.list_clients')" in base
    assert "url_for('auth.logout')" in base
