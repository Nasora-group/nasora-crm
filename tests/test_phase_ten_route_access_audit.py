"""Phase 10: regression checks for access controls on critical CRM routes."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def route_decorators(path, route_fragment):
    """Return decorators attached to the route containing route_fragment."""
    lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if ".route(" not in line or route_fragment not in line:
            continue
        end = index
        while end + 1 < len(lines) and lines[end + 1].lstrip().startswith("@"):
            end += 1
        return "\n".join(lines[index : end + 1])
    raise AssertionError(f"Route {route_fragment!r} not found in {path}")


def assert_route_access(path, route_fragment, expected_role):
    decorators = route_decorators(path, route_fragment)
    assert "@login_required" in decorators, (path, route_fragment, decorators)
    assert expected_role in decorators, (path, route_fragment, decorators)


def test_admin_reporting_and_management_routes_are_admin_only():
    assert_route_access(
        "app/routes/activity_reporting.py",
        "/admin/rapport-activite",
        '@roles_required("admin")',
    )
    assert_route_access(
        "app/routes/manager_cockpit.py",
        "/admin/cockpit-manager",
        '@roles_required("admin")',
    )
    assert_route_access(
        "app/routes/dashboard.py",
        "/admin/dashboard-direction",
        '@roles_required("admin")',
    )
    assert_route_access(
        "app/routes/evaluations.py",
        "/admin/classement",
        '@roles_required("admin")',
    )
    assert_route_access(
        "app/routes/users.py",
        "/nouveau",
        '@roles_required("admin")',
    )


def test_field_workflows_keep_expected_role_boundaries():
    assert_route_access(
        "app/routes/planning.py",
        "/saisie_planning",
        '@roles_required("commercial")',
    )
    assert_route_access(
        "app/routes/dashboard.py",
        '"/dashboard",',
        '@roles_required("commercial")',
    )
    assert_route_access(
        "app/routes/clients.py",
        "/admin/clients",
        '@roles_required("admin", "commercial")',
    )
    assert_route_access(
        "app/routes/animation_sales.py",
        "/nouvelle",
        '@roles_required("admin", "commercial", "animateur")',
    )


def test_admin_planning_management_is_not_open_to_field_roles():
    assert_route_access(
        "app/routes/planning.py",
        "/admin_plannings",
        '@roles_required("admin")',
    )
    assert_route_access(
        "app/routes/planning.py",
        "/admin_planning_generate",
        '@roles_required("admin")',
    )
