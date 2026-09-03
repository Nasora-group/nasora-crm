from types import SimpleNamespace

from app.permissions import account_is_active, division_matches, is_admin, owns_record


def user(user_id=1, role="commercial", project="nasmedic", active=True):
    return SimpleNamespace(
        id=user_id,
        role=role,
        project=project,
        is_authenticated=True,
        is_active_account=active,
    )


def record(owner_id):
    return SimpleNamespace(commercial_id=owner_id)


def test_active_account_and_role_are_normalized():
    u = user(role=" ADMIN ")
    assert account_is_active(u)
    assert is_admin(u)


def test_division_isolation_for_commercial():
    u = user(project="NASMEDIC")
    assert division_matches(u, "nasmedic")
    assert not division_matches(u, "nasderm")


def test_admin_can_access_both_divisions():
    u = user(role="admin", project="nasmedic")
    assert division_matches(u, "nasmedic")
    assert division_matches(u, "nasderm")


def test_commercial_owns_only_own_records():
    u = user(user_id=7)
    assert owns_record(u, record(7))
    assert not owns_record(u, record(8))


def test_admin_owns_any_record():
    u = user(user_id=7, role="admin")
    assert owns_record(u, record(99))


def test_inactive_user_has_no_permissions():
    u = user(active=False)
    assert not account_is_active(u)
    assert not division_matches(u, "nasmedic")
    assert not owns_record(u, record(u.id))
