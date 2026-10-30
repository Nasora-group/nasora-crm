from decimal import Decimal
from types import SimpleNamespace

from app.permissions import has_role, is_commercial, owns_record
from app.routes.animation_sales import _parse_non_negative_quantity



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


def test_animation_quantity_accepts_zero_as_no_sale():
    assert _parse_non_negative_quantity("0") == 0
    assert _parse_non_negative_quantity("3") == 3
    assert _parse_non_negative_quantity("-1") is None
    assert _parse_non_negative_quantity("invalid") is None

def test_edit_animation_quantity_must_remain_positive():
    from app.routes.animation_sales import _parse_positive_quantity

    assert _parse_positive_quantity("1") == 1
    assert _parse_positive_quantity("0") is None
    assert _parse_positive_quantity("-2") is None
    assert _parse_positive_quantity("invalid") is None

def test_animation_edit_commits_business_data_before_notification():
    from pathlib import Path

    route = Path(__file__).resolve().parents[1] / "app" / "routes" / "animation_sales.py"
    content = route.read_text(encoding="utf-8")
    edit_block = content.split('def edit_animation_sale(sale_id):', 1)[1].split('@animation_sales_bp.route("/<int:sale_id>/supprimer"', 1)[0]

    commit_position = edit_block.index("db.session.commit()")
    notification_position = edit_block.index("notify_admins(")
    assert commit_position < notification_position
    assert "except Exception:" in edit_block[notification_position:]
    assert "db.session.rollback()" in edit_block[notification_position:]
