from unittest.mock import patch

from app import create_app
from app.config import TestingConfig


def test_objectives_route_is_registered_and_admin_protected():
    app = create_app(TestingConfig)
    rules = [
        rule
        for rule in app.url_map.iter_rules()
        if rule.endpoint == "objectives.edit_objectives"
    ]

    assert rules
    assert {"GET", "POST"}.issubset(rules[0].methods)

    response = app.test_client().get("/admin/objectifs/nasmedic")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_objective_audit_action_name_is_defined():
    with patch("app.routes.objectives.audit") as audit_mock:
        audit_mock("objectives.update", target="NASMEDIC:2026")
        audit_mock.assert_called_once_with("objectives.update", target="NASMEDIC:2026")
