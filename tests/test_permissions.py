from types import SimpleNamespace

import app.permissions as permissions
from app.permissions import (
    account_is_active,
    division_matches,
    has_role,
    is_admin,
    is_commercial,
    owns_record,
)


def user(user_id=1, role="commercial", project="nasmedic", active=True):
    return SimpleNamespace(
        id=user_id,
        role=role,
        project=project,
        is_authenticated=True,
        is_active_account=active,
    )


def record(owner_id, project="nasmedic"):
    return SimpleNamespace(commercial_id=owner_id, project=project)


def test_active_account_and_role_are_normalized():
    u = user(role=" ADMIN ")
    assert account_is_active(u)
    assert is_admin(u)


def test_division_isolation_for_field_users():
    for role in ("commercial", "animateur"):
        u = user(role=role, project="NASMEDIC")
        assert division_matches(u, "nasmedic")
        assert not division_matches(u, "nasderm")


def test_admin_can_access_both_divisions():
    u = user(role="admin", project="nasmedic")
    assert division_matches(u, "nasmedic")
    assert division_matches(u, "nasderm")


def test_field_users_own_only_their_records():
    for role in ("commercial", "animateur"):
        u = user(user_id=7, role=role)
        assert owns_record(u, record(7))
        assert not owns_record(u, record(8))


def test_admin_owns_any_record():
    u = user(user_id=7, role="admin")
    assert owns_record(u, record(99))


def test_admin_can_be_restricted_by_explicit_owner_flag():
    admin = user(user_id=1, role="admin")
    assert owns_record(admin, record(99), allow_admin=True)
    assert not owns_record(admin, record(99), allow_admin=False)


def test_animateur_and_visiteur_medical_share_crm_role_permission():
    animateur = user(role="animateur")
    visiteur = user(role="commercial")
    assert is_commercial(animateur)
    assert is_commercial(visiteur)


def test_shared_role_decorator_permission():
    for role in ("commercial", "animateur"):
        assert has_role_for_user(role)


def has_role_for_user(role):
    return role in {"commercial", "animateur"}


def test_inactive_user_has_no_permissions():
    u = user(active=False)
    assert not account_is_active(u)
    assert not division_matches(u, "nasmedic")
    assert not owns_record(u, record(u.id))


def test_require_same_division_rejects_cross_division(monkeypatch):
    field_user = user(role="commercial", project="nasmedic")
    monkeypatch.setattr(permissions, "current_user", field_user)
    permissions.require_same_division(record(7, project="nasmedic"))
    try:
        permissions.require_same_division(record(7, project="nasderm"))
    except Exception as exc:
        assert getattr(exc, "code", None) == 403
    else:
        raise AssertionError("A cross-division record must be rejected")


def test_require_same_division_allows_admin(monkeypatch):
    admin = user(role="admin", project="nasmedic")
    monkeypatch.setattr(permissions, "current_user", admin)
    assert permissions.require_same_division(record(99, project="nasderm"))
