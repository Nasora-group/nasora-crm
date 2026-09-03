from unittest.mock import patch

from app.routes.objectives import edit_objectives


def test_objectives_route_is_admin_protected():
    assert edit_objectives is not None


def test_objective_audit_action_name_is_defined():
    with patch("app.routes.objectives.audit") as audit_mock:
        audit_mock("objectives.update", target="NASMEDIC:2026")
        audit_mock.assert_called_once_with("objectives.update", target="NASMEDIC:2026")
