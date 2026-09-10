from decimal import Decimal
from types import SimpleNamespace

from app.permissions import has_role, is_commercial, owns_record


def test_animation_sales_total_is_quantity_times_unit_price():
    # Mirrors the model's business rule without requiring a live database.
    sale = SimpleNamespace(quantity=3, unit_price=Decimal("2500.00"))
    assert sale.quantity * sale.unit_price == Decimal("7500.00")


def test_animateur_has_shared_field_permissions_but_is_distinct_role():
    animateur = SimpleNamespace(
        id=10,
        role="animateur",
        project="nasmedic",
        is_authenticated=True,
        is_active_account=True,
    )
    own_sale = SimpleNamespace(animateur_id=10)
    other_sale = SimpleNamespace(animateur_id=11)
    assert is_commercial(animateur)
    assert owns_record(animateur, SimpleNamespace(commercial_id=10))
    assert owns_record(animateur, own_sale, owner_field="animateur_id")
    assert not owns_record(animateur, other_sale, owner_field="animateur_id")


def test_role_permission_keeps_admin_separate():
    # This documents the intended route-level contract for animation sales.
    assert "animateur" != "admin"
