from pathlib import Path


def test_role_based_simplification_styles_are_loaded_and_responsive():
    base = Path("app/templates/base.html").read_text(encoding="utf-8")
    css = Path("app/static/css/role-based-simplification.css").read_text(encoding="utf-8")

    assert "role-based-simplification.css" in base
    assert ".ns-role-home__grid" in css
    assert "@media(max-width:560px)" in css
    assert "prefers-reduced-motion" in css


def test_animator_dashboard_exposes_direct_animation_actions():
    dashboard = Path("app/templates/dashboard.html").read_text(encoding="utf-8")

    assert "current_user.role == 'animateur'" in dashboard
    assert "animation_sales.new_animation_sale" in dashboard
    assert "animation_sales.my_history" in dashboard
    assert "animation-home-title" in dashboard


def test_admin_dashboard_has_role_specific_quick_access_without_removing_existing_navigation():
    dashboard = Path("app/templates/admin_dashboard.html").read_text(encoding="utf-8")

    assert "Accès rapides administrateur" in dashboard
    assert "planning.admin_plannings" in dashboard
    assert "dashboard.direction" in dashboard
    assert "users.list_users" in dashboard
    assert "evaluations.classement" in dashboard
    assert "dashboard-nav-actions" in dashboard


def test_animation_form_has_mobile_friendly_layout_hooks_and_keeps_form_fields():
    form = Path("app/templates/animation_sale_form.html").read_text(encoding="utf-8")

    assert 'class="crm-page ns-animation-form"' in form
    assert 'class="ns-form-meta"' in form
    assert 'class="ns-product-grid"' in form
    assert 'name="pharmacy_name"' in form
    assert 'name="animation_date"' in form
    assert 'name="animation_evidence"' in form
    assert "animation-total" in form


def test_visitor_dashboard_exposes_direct_planning_and_prospection_actions():
    dashboard = Path("app/templates/dashboard.html").read_text(encoding="utf-8")

    assert "visitor-home-title" in dashboard
    assert "planning.visualiser" in dashboard
    assert "nouvelle-prospection" in dashboard
    assert "clients.list_clients" in dashboard


def test_prospection_form_is_responsive_without_removing_business_fields():
    css = Path("app/static/css/role-based-simplification.css").read_text(encoding="utf-8")
    form = Path("app/templates/dashboard.html").read_text(encoding="utf-8")

    assert ".prospection-panel .prospection-form" in css
    assert "@media(max-width:700px)" in css
    assert "form.date" in form
    assert "form.structure" in form
    assert "form.nom_structure" in form
    assert "form.profils_prospect" in form
    assert "form.produits_presentes" in form
    assert "form.produits_prescrits" in form

 
def test_phase_two_visitor_quick_actions_are_mobile_only_and_preserve_existing_routes():
    dashboard = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
    base = Path("app/templates/base.html").read_text(encoding="utf-8")
    css = Path("app/static/css/phase2-visitor-quick-actions.css").read_text(encoding="utf-8")

    assert "current_user.role == 'commercial'" in dashboard
    assert 'class="ns-mobile-quick-actions"' in dashboard
    assert 'href="#nouvelle-prospection"' in dashboard
    assert "planning.visualiser" in dashboard
    assert "phase2-visitor-quick-actions.css" in base
    assert "@media(max-width:760px)" in css
    assert "env(safe-area-inset-bottom, 0px)" in css
    assert "prefers-reduced-motion" in css
