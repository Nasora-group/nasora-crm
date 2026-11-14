import io

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Laboratory, LaboratoryProduct, LaboratorySale, User


@pytest.fixture()
def laboratory_client():
    app = create_app(TestingConfig)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY="laboratory-test")
    with app.app_context():
        db.create_all()
        admin = User(username="lab_admin", password=generate_password_hash("secret"), role="admin", project="nasmedic", is_active_account=True)
        staff = User(username="lab_staff", password=generate_password_hash("secret"), role="commercial", project="nasmedic", is_active_account=True)
        db.session.add_all([admin, staff])
        db.session.commit()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def login(client, username="lab_admin"):
    response = client.post("/login", data={"username": username, "password": "secret"})
    assert response.status_code == 302


def test_laboratory_module_is_admin_only(laboratory_client):
    assert laboratory_client.get("/admin/laboratoires/").status_code == 302
    login(laboratory_client, "lab_staff")
    assert laboratory_client.get("/admin/laboratoires/").status_code == 403


def test_admin_can_create_laboratory_with_staff_and_objectives(laboratory_client):
    login(laboratory_client)
    response = laboratory_client.post(
        "/admin/laboratoires/nouveau",
        data={
            "name": "Laboratoire Démo",
            "slug": "laboratoire-demo",
            "currency": "XOF",
            "section": "nasderm",
            "address": "Dakar Plateau",
            "monthly_objective": "1500000",
            "annual_objective": "18000000",
            "staff_ids": ["2"],
            "is_active": "on",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Laboratoire créé".encode() in response.data
    with laboratory_client.application.app_context():
        lab = Laboratory.query.one()
        assert lab.slug == "laboratoire-demo"
        assert lab.currency == "XOF"
        assert lab.section == "nasderm"
        assert str(lab.monthly_objective) == "1500000.00"
        assert [user.username for user in lab.staff] == ["lab_staff"]


def test_catalog_import_adds_and_updates_products_without_quantity(laboratory_client):
    login(laboratory_client)
    laboratory_client.post(
        "/admin/laboratoires/nouveau",
        data={"name": "Alpha Pharma", "currency": "EUR", "is_active": "on"},
        follow_redirects=True,
    )
    with laboratory_client.application.app_context():
        lab = Laboratory.query.one()
        lab_id = lab.id
        product = LaboratoryProduct(laboratory_id=lab_id, reference="REF-01", name="Ancien nom", price_ht="2.00")
        db.session.add(product)
        db.session.commit()
    csv_data = "reference,name,price_ht\nREF-01,Nouveau nom,3.50\nREF-02,Produit B,4.20\n"
    response = laboratory_client.post(
        f"/admin/laboratoires/{lab_id}/produits/importer",
        data={"catalog_file": (io.BytesIO(csv_data.encode("utf-8")), "catalogue.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "1 produit(s) ajouté(s), 1 mis à jour".encode() in response.data
    with laboratory_client.application.app_context():
        products = LaboratoryProduct.query.filter_by(laboratory_id=lab_id).order_by(LaboratoryProduct.reference).all()
        assert len(products) == 2
        assert products[0].name == "Nouveau nom"
        assert str(products[0].price_ht) == "3.50"
        assert not hasattr(products[0], "quantity")


def test_catalog_import_rejects_quantity_column_atomically(laboratory_client):
    login(laboratory_client)
    laboratory_client.post("/admin/laboratoires/nouveau", data={"name": "Beta", "is_active": "on"}, follow_redirects=True)
    with laboratory_client.application.app_context():
        lab_id = Laboratory.query.one().id
    csv_data = "reference,name,price_ht,quantity\nR1,Produit 1,2.50,10\n"
    response = laboratory_client.post(
        f"/admin/laboratoires/{lab_id}/produits/importer",
        data={"catalog_file": (io.BytesIO(csv_data.encode()), "catalogue.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "aucune colonne de quantité".encode() in response.data
    with laboratory_client.application.app_context():
        assert LaboratoryProduct.query.filter_by(laboratory_id=lab_id).count() == 0


def test_universal_templates_have_no_quantity_column(laboratory_client):
    login(laboratory_client)
    response = laboratory_client.get("/admin/laboratoires/modele/csv")
    assert response.status_code == 200
    assert response.data.decode("utf-8-sig").strip() == "reference,name,price_ht"


def test_non_admin_cannot_download_laboratory_logo(laboratory_client):
    login(laboratory_client)
    laboratory_client.post("/admin/laboratoires/nouveau", data={"name": "Gamma", "is_active": "on"}, follow_redirects=True)
    with laboratory_client.application.app_context():
        lab_id = Laboratory.query.one().id
    laboratory_client.post("/logout", follow_redirects=True)
    login(laboratory_client, "lab_staff")
    assert laboratory_client.get(f"/admin/laboratoires/{lab_id}/logo").status_code == 403

def test_dynamic_laboratory_sales_are_saved_and_counted(laboratory_client):
    login(laboratory_client)
    laboratory_client.post(
        "/admin/laboratoires/nouveau",
        data={"name": "Nouveau laboratoire", "currency": "XOF", "section": "nasderm", "is_active": "on"},
        follow_redirects=True,
    )
    with laboratory_client.application.app_context():
        lab = Laboratory.query.one()
        product = LaboratoryProduct(laboratory_id=lab.id, reference="N-01", name="Produit test", price_ht="2500")
        db.session.add(product)
        db.session.commit()
        lab_id, product_id = lab.id, product.id
    response = laboratory_client.post(
        f"/admin/laboratoires/{lab_id}/ventes",
        data={"sale_date": "2026-11-14", f"quantity_{product_id}": "3"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with laboratory_client.application.app_context():
        sale = LaboratorySale.query.one()
        assert sale.laboratory_id == lab_id
        assert sale.quantity == 3
        assert str(sale.price) == "2500.00"
        assert sale.project == "nasderm"


def test_laboratory_sales_import_is_atomic(laboratory_client):
    login(laboratory_client)
    laboratory_client.post("/admin/laboratoires/nouveau", data={"name": "Import Lab", "is_active": "on"}, follow_redirects=True)
    with laboratory_client.application.app_context():
        lab = Laboratory.query.one()
        db.session.add(LaboratoryProduct(laboratory_id=lab.id, reference="R1", name="Produit 1", price_ht="10"))
        db.session.commit()
        lab_id = lab.id
    csv_data = "date,reference,quantity,price\\n2026-11-14,R1,2,12.50\\n"
    response = laboratory_client.post(
        f"/admin/laboratoires/{lab_id}/ventes/importer",
        data={"sales_file": (io.BytesIO(csv_data.encode()), "ventes.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    with laboratory_client.application.app_context():
        sale = LaboratorySale.query.one()
        assert sale.is_imported is True
        assert sale.quantity == 2
        assert str(sale.price) == "12.50"
