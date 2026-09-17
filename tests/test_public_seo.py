from app import create_app
from app.config import TestingConfig


def test_public_seo_routes_are_available():
    app = create_app(TestingConfig)
    client = app.test_client()

    robots = client.get("/robots.txt")
    sitemap = client.get("/sitemap.xml")

    assert robots.status_code == 200
    assert robots.mimetype == "text/plain"
    assert "Sitemap:" in robots.get_data(as_text=True)
    assert "Disallow: /api/" in robots.get_data(as_text=True)

    assert sitemap.status_code == 200
    assert sitemap.mimetype == "application/xml"
    xml = sitemap.get_data(as_text=True)
    assert "https://" not in xml or "<urlset" in xml
    assert "/rgpd" in xml
    assert "/cgu" in xml


def test_api_responses_are_marked_non_indexable():
    app = create_app(TestingConfig)
    client = app.test_client()

    response = client.get("/api/nonexistent")

    assert response.status_code == 404
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow, noarchive"
