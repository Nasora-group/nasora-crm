from types import SimpleNamespace

from app.permissions import division_matches, owns_record, require_division
from werkzeug.exceptions import Forbidden


def user(role, project, user_id=1):
    return SimpleNamespace(
        id=user_id,
        role=role,
        project=project,
        is_authenticated=True,
        is_active_account=True,
    )


def test_admin_can_access_both_divisions():
    admin = user("admin", "nasmedic")
    assert division_matches(admin, "nasmedic")
    assert division_matches(admin, "nasderm")


def test_field_user_is_limited_to_own_division():
    vm = user("commercial", "nasmedic", 7)
    assert division_matches(vm, "nasmedic")
    assert not division_matches(vm, "nasderm")


def test_field_user_cannot_claim_another_user_record():
    vm = user("commercial", "nasmedic", 7)
    own = SimpleNamespace(commercial_id=7)
    other = SimpleNamespace(commercial_id=8)
    assert owns_record(vm, own)
    assert not owns_record(vm, other)


def test_require_division_rejects_cross_division_access(monkeypatch):
    vm = user("commercial", "nasmedic", 7)
    monkeypatch.setattr("app.permissions.current_user", vm)
    try:
        require_division("nasderm")
    except Forbidden:
        return
    raise AssertionError("Cross-division access must be rejected")
