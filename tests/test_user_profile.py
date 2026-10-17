import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import User, UserProfile


@pytest.fixture()
def profile_client():
    app = create_app(TestingConfig)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY="profile-test")
    with app.app_context():
        db.create_all()
        user = User(
            username="profile_test",
            password=generate_password_hash("profile-password"),
            role="commercial",
            project="nasmedic",
            zone="DAKAR",
            is_active_account=True,
        )
        admin = User(
            username="admin_test",
            password=generate_password_hash("admin-password"),
            role="admin",
            project="nasmedic",
            zone=None,
            is_active_account=True,
        )
        db.session.add_all([user, admin])
        db.session.commit()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def login(client):
    response = client.post(
        "/login",
        data={"username": "profile_test", "password": "profile-password"},
    )
    assert response.status_code == 302


def test_profile_page_requires_login(profile_client):
    response = profile_client.get("/mon-profil")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_profile_can_save_contact_information(profile_client):
    login(profile_client)
    response = profile_client.post(
        "/mon-profil",
        data={
            "first_name": "Awa",
            "last_name": "Ndiaye",
            "email": "awa@example.com",
            "phone": "+221 77 000 00 00",
            "job_title": "Visiteuse médicale",
            "city": "Dakar",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Ton profil a été enregistré".encode() in response.data
    with profile_client.application.app_context():
        profile = UserProfile.query.one()
        assert profile.first_name == "Awa"
        assert profile.last_name == "Ndiaye"
        assert profile.email == "awa@example.com"
        assert profile.city == "Dakar"


def test_profile_accepts_png_photo_and_serves_it_privately(profile_client):
    login(profile_client)
    png_signature = b"\x89PNG\r\n\x1a\n" + b"profile-image-test"
    response = profile_client.post(
        "/mon-profil",
        data={
            "first_name": "Awa",
            "photo": ( __import__("io").BytesIO(png_signature), "avatar.png", "image/png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    photo = profile_client.get("/mon-profil/photo")
    assert photo.status_code == 200
    assert photo.mimetype == "image/png"
    assert photo.data == png_signature
    assert "no-store" in photo.headers["Cache-Control"]


def test_profile_rejects_unsupported_photo_type(profile_client):
    login(profile_client)
    response = profile_client.post(
        "/mon-profil",
        data={"photo": (__import__("io").BytesIO(b"not-an-image"), "avatar.gif", "image/gif")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Format de photo non accepté".encode() in response.data


def test_profile_photo_requires_login(profile_client):
    response = profile_client.get("/mon-profil/photo")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_profile_rejects_photo_larger_than_two_megabytes(profile_client):
    import io

    login(profile_client)
    response = profile_client.post(
        "/mon-profil",
        data={
            "photo": (io.BytesIO(b"\\x89PNG\\r\\n\\x1a\\n" + b"x" * (2 * 1024 * 1024)), "large.png", "image/png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "La photo ne doit pas dépasser 2 Mo".encode() in response.data


def test_profile_rejects_invalid_email_without_saving_it(profile_client):
    login(profile_client)
    response = profile_client.post(
        "/mon-profil",
        data={"email": "not-an-email"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Saisis une adresse e-mail valide".encode() in response.data
    with profile_client.application.app_context():
        profile = UserProfile.query.one()
        assert profile.email is None



def test_admin_user_list_displays_uploaded_profile_photo(profile_client):
    login(profile_client)
    png_signature = b"\\x89PNG\\r\\n\\x1a\\n" + b"profile-image-test"
    profile_client.post(
        "/mon-profil",
        data={"first_name": "Awa", "last_name": "Ndiaye",
              "photo": (__import__("io").BytesIO(png_signature), "awa.png", "image/png")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    profile_client.post(
        "/logout",
        follow_redirects=True,
    )
    response = profile_client.post(
        "/login",
        data={"username": "admin_test", "password": "admin-password"},
    )
    assert response.status_code == 302

    listing = profile_client.get("/admin/utilisateurs/")
    assert listing.status_code == 200
    assert b"/admin/utilisateurs/" in listing.data
    assert b"Photo de Awa" in listing.data
    assert b"Awa Ndiaye" in listing.data


def test_admin_photo_endpoint_requires_admin_role(profile_client):
    login(profile_client)
    response = profile_client.get("/admin/utilisateurs/1/photo")
    assert response.status_code == 403
