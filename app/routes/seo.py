from html import escape

from flask import Blueprint, Response, current_app, url_for

seo_bp = Blueprint("seo", __name__)


@seo_bp.get("/robots.txt")
def robots():
    """Robots policy: index only public pages, never CRM/private/API paths."""
    sitemap = url_for("seo.sitemap", _external=True)
    body = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin",
            "Disallow: /api/",
            "Disallow: /dashboard",
            "Disallow: /manager",
            "Disallow: /planning",
            "Disallow: /clients",
            "Disallow: /stock",
            "Disallow: /users",
            "Disallow: /evaluations",
            "Disallow: /prospections",
            "Disallow: /sales",
            "Disallow: /login",
            f"Sitemap: {sitemap}",
            "",
        ]
    )
    response = Response(body, mimetype="text/plain")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@seo_bp.get("/sitemap.xml")
def sitemap():
    """XML sitemap containing public, crawlable pages only."""
    public_endpoints = ["auth.home", "legal.rgpd", "legal.cgu"]
    urls = []
    for endpoint in public_endpoints:
        try:
            urls.append(url_for(endpoint, _external=True))
        except Exception:
            current_app.logger.warning("Endpoint sitemap indisponible: %s", endpoint)

    items = "".join(f"<url><loc>{escape(url)}</loc></url>" for url in urls)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{items}</urlset>"
    )
    response = Response(xml, mimetype="application/xml")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@seo_bp.get("/healthz")
def healthz():
    """Lightweight process health endpoint; intentionally does not touch the database."""
    return Response("ok\n", mimetype="text/plain")
