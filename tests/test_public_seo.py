from app import create_app
from app.config import TestingConfig


def test_public_seo_routes_are_available():
    app = create_app(TestingConfig)
    client = app.test_client()

    robots = client.get("/robots.txt")
    sitemap = client.get("/sitemap.xml")
    health = client.get("/healthz")

    assert robots.status_code == 200
    assert robots.mimetype == "text/plain"
    assert robots.headers["Cache-Control"] == "public, max-age=3600"
    robots_text = robots.get_data(as_text=True)
    assert "Sitemap:" in robots_text
    assert "Disallow: /api/" in robots_text
    assert "Disallow: /login" in robots_text

    assert sitemap.status_code == 200
    assert sitemap.mimetype == "application/xml"
    assert sitemap.headers["Cache-Control"] == "public, max-age=3600"
    xml = sitemap.get_data(as_text=True)
    assert "<urlset" in xml
    assert "/rgpd" in xml
    assert "/cgu" in xml
    assert "/login" not in xml
    assert "&amp;" not in xml

    assert health.status_code == 200
    assert health.get_data(as_text=True) == "ok\n"


def test_api_responses_are_marked_non_indexable():
    app = create_app(TestingConfig)
    client = app.test_client()

    response = client.get("/api/nonexistent")

    assert response.status_code == 404
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow, noarchive"
