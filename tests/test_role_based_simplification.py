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


def test_phase_three_admin_tools_are_grouped_without_removing_existing_routes():
    dashboard = Path("app/templates/admin_dashboard.html").read_text(encoding="utf-8")
    base = Path("app/templates/base.html").read_text(encoding="utf-8")
    css = Path("app/static/css/phase3-admin-dashboard.css").read_text(encoding="utf-8")

    assert '<details class="dashboard-tools-disclosure">' in dashboard
    assert "</details>" in dashboard
    assert "sales_history" in dashboard
    assert "products.list_products" in dashboard
    assert "stock.entry" in dashboard
    assert "stock.available" in dashboard
    assert "stock.history" in dashboard
    assert "planning.admin_plannings" in dashboard
    assert "phase3-admin-dashboard.css" in base
    assert ".dashboard-tools-disclosure" in css
    assert "@media" in css

def test_phase_four_animator_workflow_styles_preserve_form_fields_and_totals():
    base = Path("app/templates/base.html").read_text(encoding="utf-8")
    form = Path("app/templates/animation_sale_form.html").read_text(encoding="utf-8")
    css = Path("app/static/css/phase4-animator-workflow.css").read_text(encoding="utf-8")

    assert "phase4-animator-workflow.css" in base
    assert "ns-animation-form" in form
    assert 'name="pharmacy_name"' in form
    assert 'name="animation_date"' in form
    assert 'name="animation_evidence"' in form
    assert 'class="sale-unit-price"' in form
    assert 'class="sale-quantity"' in form
    assert 'id="animation-total"' in form
    assert "updateTotal()" in form
    assert ".ns-animation-form .ns-product-scroll" in css
    assert ".ns-animation-form .ns-form-footer" in css
    assert "@media(max-width:700px)" in css
    assert "prefers-reduced-motion" in css


def test_phase_five_planning_week_remains_complete_and_responsive():
    base = Path("app/templates/base.html").read_text(encoding="utf-8")
    planning = Path("app/templates/visualiser_planning.html").read_text(encoding="utf-8")
    week_card = Path("app/templates/_planning_week_card.html").read_text(encoding="utf-8")
    css = Path("app/static/css/phase5-planning-mobile.css").read_text(encoding="utf-8")

    assert "phase5-planning-mobile.css" in base
    assert "planning-week-card" in week_card
    assert "planning-days-row" in week_card
    assert "('samedi','Samedi')" in week_card
    assert "('dimanche','Dimanche')" in week_card
    assert "planning.saisie" in planning
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in css
    assert "@media(max-width:380px)" in css
    assert "planning-badge-nom" in css


def test_phase_six_animation_history_is_mobile_friendly_and_keeps_history_controls():
    base = Path("app/templates/base.html").read_text(encoding="utf-8")
    history = Path("app/templates/animation_sales_history.html").read_text(encoding="utf-8")
    css = Path("app/static/css/phase6-animation-history.css").read_text(encoding="utf-8")
    route = Path("app/routes/animation_sales.py").read_text(encoding="utf-8")

    assert "phase6-animation-history.css" in base
    assert 'class="crm-page ns-animation-history"' in history
    assert 'class="ns-history-filter-form"' in history
    assert 'class="ns-history-summary-content"' in history
    assert 'name="month"' in history
    assert 'name="pharmacy"' in history
    assert "name=\"animateur_id\"" in history
    assert "animation_sales.edit_animation_sale" in history
    assert "animation_sales.delete_animation_sale" in history
    assert ".ns-animation-history .ns-history-filter-form" in css
    assert "@media(max-width:600px)" in css
    assert "prefers-reduced-motion" in css
    assert 'if current_user.role == "animateur":' in route

def test_phase_seven_direction_dashboard_indicators_are_mobile_friendly():
    base = Path("app/templates/base.html").read_text(encoding="utf-8")
    dashboard = Path("app/templates/admin_dashboard.html").read_text(encoding="utf-8")
    css = Path("app/static/css/phase7-dashboard-mobile.css").read_text(encoding="utf-8")

    assert "phase7-dashboard-mobile.css" in base
    assert "direction-division-grid" in dashboard
    assert "crm-kpi-grid" in dashboard
    assert "direction-metrics" in dashboard
    assert "@media (max-width: 640px)" in css
    assert "@media (max-width: 380px)" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in css
    assert "prefers-reduced-motion" in css
    assert "word-break: normal" in css


def test_phase_eight_reporting_control_uses_existing_data_and_covers_full_week():
    base = Path("app/templates/base.html").read_text(encoding="utf-8")
    template = Path("app/templates/manager_cockpit.html").read_text(encoding="utf-8")
    route = Path("app/routes/manager_cockpit.py").read_text(encoding="utf-8")
    css = Path("app/static/css/phase8-reporting-control.css").read_text(encoding="utf-8")

    assert "phase8-reporting-control.css" in base
    assert "Contrôle des saisies quotidiennes" in template
    assert "reporting_start.strftime" in template
    assert "reporting_rows" in template
    assert "Prospection" in route
    assert "AnimationSale" in route
    assert '("samedi", 5), ("dimanche", 6)' in route
    assert "À vérifier" in route
    assert "reporting_last_day" in route
    assert ".reporting-status--warning" in css
    assert "@media(max-width:700px)" in css
