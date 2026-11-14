from datetime import date
from werkzeug.security import generate_password_hash

import pytest
from flask_login import login_user

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import (
    User, Laboratory, LaboratoryProduct, LaboratorySale,
)
from app.models_stock import StockEntry


@pytest.fixture()
def scoped_lab_app():
    app = create_app(TestingConfig)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY="lab-scope-test")
    with app.app_context():
        db.create_all()
        admin = User(
            username="scope_admin", password=generate_password_hash("secret"),
            role="admin", project="nasmedic", is_active_account=True,
        )
        rep = User(
            username="scope_rep", password=generate_password_hash("secret"),
            role="commercial", project="nasmedic", is_active_account=True,
        )
        db.session.add_all([admin, rep])
        db.session.flush()

        legacy_labs = [
            Laboratory(
                name="Eric Favre", slug="legacy-eric-favre", legacy_supplier_slug="eric_favre",
                section="nasmedic", currency="EUR", is_active=True,
            ),
            Laboratory(
                name="3 Chênes Pharma", slug="legacy-trois-chenes", legacy_supplier_slug="trois_chene",
                section="nasmedic", currency="EUR", is_active=True,
            ),
            Laboratory(
                name="Gilbert", slug="legacy-gilbert", legacy_supplier_slug="gilbert",
                section="nasderm", currency="XOF", is_active=True,
            ),
        ]
        assigned = Laboratory(
            name="Laboratoire attribué", slug="lab-attribue",
            section="nasmedic", currency="XOF", is_active=True,
        )
        unassigned = Laboratory(
            name="Laboratoire non attribué", slug="lab-non-attribue",
            section="nasmedic", currency="XOF", is_active=True,
        )
        assigned.staff.append(rep)
        db.session.add_all([*legacy_labs, assigned, unassigned])
        db.session.flush()

        allowed_product = LaboratoryProduct(
            laboratory_id=assigned.id, reference="AL-01",
            name="Produit autorisé", price_ht="10", is_active=True,
        )
        hidden_product = LaboratoryProduct(
            laboratory_id=unassigned.id, reference="NA-01",
            name="Produit non attribué", price_ht="100", is_active=True,
        )
        db.session.add_all([allowed_product, hidden_product])
        db.session.flush()

        db.session.add_all([
            LaboratorySale(
                laboratory_id=assigned.id, product_id=allowed_product.id,
                commercial_id=rep.id, quantity=3, price="10",
                date=date(2026, 11, 14), project="nasmedic",
            ),
            LaboratorySale(
                laboratory_id=unassigned.id, product_id=hidden_product.id,
                commercial_id=rep.id, quantity=2, price="100",
                date=date(2026, 11, 14), project="nasmedic",
            ),
            StockEntry(
                week_start=date(2026, 11, 9), division="nasmedic",
                laboratory=assigned.name, product_name=allowed_product.name,
                wholesaler="duopharm", quantity=5, created_by_id=admin.id,
            ),
            StockEntry(
                week_start=date(2026, 11, 9), division="nasmedic",
                laboratory=unassigned.name, product_name=hidden_product.name,
                wholesaler="duopharm", quantity=99, created_by_id=admin.id,
            ),
        ])
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


def test_revenue_dashboard_only_counts_assigned_laboratories(scoped_lab_app):
    from app.routes.revenue import _monthly_revenue_for_division

    with scoped_lab_app.test_request_context("/"):
        rep = User.query.filter_by(username="scope_rep").one()
        assigned = Laboratory.query.filter_by(slug="lab-attribue").one()
        login_user(rep)
        labels, totals, combined = _monthly_revenue_for_division("nasmedic", scope_to_commercial=False)

        assert "2026-11" in labels
        assert combined["2026-11"] == {f"laboratory_{assigned.id}": 30.0}
        assert totals[labels.index("2026-11")] == 30.0


def test_vm_cockpit_only_counts_assigned_laboratories(scoped_lab_app):
    from app.routes.vm_cockpit import (
        _commercial_revenue, _commercial_revenue_rows, _commercial_revenue_detail,
    )

    with scoped_lab_app.app_context():
        rep = User.query.filter_by(username="scope_rep").one()
        monthly = _commercial_revenue(rep.id, "nasmedic")
        rows, suppliers, _labels = _commercial_revenue_rows(rep.id, "nasmedic")
        detail = _commercial_revenue_detail(rep.id, "nasmedic", "2026-11")

        assert monthly == [("2026-11", 30.0)]
        assert [supplier[1] for supplier in suppliers] == ["Laboratoire attribué"]
        assert rows[0]["total"] == 30.0
        assert sum(item["revenue"] for item in detail) == 30.0
        assert all(item["supplier"] == "Laboratoire attribué" for item in detail)


def test_management_cockpit_includes_new_laboratory_sales(scoped_lab_app):
    from app.routes.manager_cockpit import _revenue_for_range

    with scoped_lab_app.app_context():
        total, products, suppliers = _revenue_for_range(
            "nasmedic", date(2026, 11, 1), date(2026, 12, 1)
        )
        assert total == 230.0
        assert products["Produit autorisé"] == 3
        assert products["Produit non attribué"] == 2
        assert suppliers["Laboratoire attribué"] == 30.0
        assert suppliers["Laboratoire non attribué"] == 200.0


def test_stock_hides_ambiguous_duplicate_laboratory_names(scoped_lab_app):
    from app.routes.stock import _snapshot

    with scoped_lab_app.test_request_context("/"):
        rep = User.query.filter_by(username="scope_rep").one()
        login_user(rep)
        db.session.add(Laboratory(
            name="Laboratoire attribué", slug="lab-duplicate-name",
            section="nasmedic", currency="XOF", is_active=True,
        ))
        db.session.commit()
        assert _snapshot(date(2026, 11, 9)) == {}


def test_stock_catalog_and_history_only_show_assigned_laboratories(scoped_lab_app):
    from app.routes.stock import _catalog, _snapshot

    with scoped_lab_app.test_request_context("/"):
        rep = User.query.filter_by(username="scope_rep").one()
        login_user(rep)
        catalog = _catalog()
        snapshot = _snapshot(date(2026, 11, 9))

        assert {item["laboratory"] for item in catalog} == {"Laboratoire attribué"}
        assert all(item["product"] == "Produit autorisé" for item in catalog)
        assert {key[1] for key in snapshot} == {"Laboratoire attribué"}
        assert all(entry.quantity == 5 for entry in snapshot.values())
