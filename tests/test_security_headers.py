from app import create_app
from app.config import TestingConfig


def test_security_headers_are_present():
    app = create_app(TestingConfig)
    client = app.test_client()

    response = client.get("/")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == "geolocation=(self), microphone=(), camera=()"
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert response.headers["X-Permitted-Cross-Domain-Policies"] == "none"


def test_login_response_is_not_cached():
    app = create_app(TestingConfig)
    client = app.test_client()

    response = client.get("/login")

    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
