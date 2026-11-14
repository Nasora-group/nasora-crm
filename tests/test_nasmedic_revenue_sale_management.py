from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import User, EricFavreProduct, EricFavreSale, TroisCheneProduct, TroisCheneSale


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY="test")
    with app.app_context():
        db.create_all()
        admin = User(username="admin_nasmedic_revenue", password=generate_password_hash("password"), role="admin", project="nasmedic", is_active_account=True)
        product = EricFavreProduct(name="Produit test", default_price=Decimal("4.50"), is_active=True)
        other_product = TroisCheneProduct(name="Produit 3 Chênes", default_price=Decimal("5.00"), is_active=True)
        db.session.add_all([admin, product, other_product])
        db.session.flush()
        db.session.add_all([
            EricFavreSale(product_id=product.id, quantity=3, price=Decimal("4.50"), date=date(2026, 10, 5), project="nasmedic", commercial_id=admin.id),
            TroisCheneSale(product_id=other_product.id, quantity=2, price=Decimal("5.00"), date=date(2026, 10, 6), project="nasmedic", commercial_id=admin.id),
        ])
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client):
    return client.post("/login", data={"username": "admin_nasmedic_revenue", "password": "password"}, follow_redirects=False)


def test_nasmedic_month_detail_lists_individual_sales_and_admin_actions(client):
    login(client)
    response = client.get("/monthly_revenue_detail_nasmedic/2026-10")
    assert response.status_code == 200
    assert b"Produit test" in response.data
    assert "Produit 3 Chênes".encode("utf-8") in response.data
    assert b"Modifier" in response.data
    assert b"Supprimer" in response.data


def test_nasmedic_month_detail_can_filter_sales_by_date(client):
    login(client)
    response = client.get("/monthly_revenue_detail_nasmedic/2026-10?date=2026-10-05")
    assert response.status_code == 200
    assert b"Produit test" in response.data
    assert "Produit 3 Chênes".encode("utf-8") not in response.data


def test_admin_can_edit_individual_nasmedic_sale_and_revenue_values(client, app):
    login(client)
    with app.app_context():
        sale = EricFavreSale.query.one()
        sale_id = sale.id
    response = client.post(
        f"/monthly_revenue_detail_nasmedic/2026-10/eric_favre/{sale_id}/edit",
        data={"date": "2026-10-07", "quantity": "8", "price": "6.25", "submit": "Enregistrer"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    with app.app_context():
        sale = EricFavreSale.query.get(sale_id)
        assert sale.date == date(2026, 10, 7)
        assert sale.quantity == 8
        assert sale.price == Decimal("6.25")


def test_admin_can_delete_only_the_selected_nasmedic_sale(client, app):
    login(client)
    with app.app_context():
        sale = EricFavreSale.query.one()
        sale_id = sale.id
    response = client.post(
        f"/monthly_revenue_detail_nasmedic/2026-10/eric_favre/{sale_id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 302
    with app.app_context():
        assert EricFavreSale.query.count() == 0
        assert TroisCheneSale.query.count() == 1
