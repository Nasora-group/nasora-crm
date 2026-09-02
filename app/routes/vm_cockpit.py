from calendar import monthrange
from collections import Counter
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, render_template
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db
from app.models import User, Prospection, SUPPLIERS, DIVISION_SUPPLIERS
from app.models_clients import Client, ClientVisit
from app.utils import roles_required
from app.visit_metrics import unique_visit_count_for_commercial

vm_cockpit_bp = Blueprint("vm_cockpit", __name__)


def _unique_visit_rows_for_commercial(commercial_id, limit=None, date_filter=None):
    """Retourne une seule ligne représentative par visite métier.

    La clé métier est (commercial, professionnel, date). Les doublons historiques
    restent en base mais ne doivent jamais gonfler l'affichage du cockpit.
    """
    ranked = (
        db.session.query(
            ClientVisit.id.label("visit_id"),
            func.row_number().over(
                partition_by=(ClientVisit.commercial_id, ClientVisit.client_id, ClientVisit.date),
                order_by=ClientVisit.id.desc(),
            ).label("rn"),
        )
        .filter(ClientVisit.commercial_id == commercial_id, ClientVisit.is_duplicate.is_(False))
    )
    if date_filter is not None:
        ranked = ranked.filter(ClientVisit.date == date_filter)
    ranked = ranked.subquery()
    query = ClientVisit.query.join(ranked, ClientVisit.id == ranked.c.visit_id).filter(ranked.c.rn == 1).order_by(ClientVisit.date.desc(), ClientVisit.id.desc())
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def _commercial_revenue(commercial_id, division):
    """Retourne le CA mensuel du commercial, limité à sa division/projet."""
    combined = {}
    for slug in DIVISION_SUPPLIERS.get(division, []):
        sale_model = SUPPLIERS[slug]["sale_model"]
        month_expr = func.strftime("%Y-%m", sale_model.date) if db.engine.dialect.name == "sqlite" else func.to_char(sale_model.date, "YYYY-MM")
        amount_expr = func.coalesce(sale_model.quantity, 0) * func.coalesce(sale_model.price, 0)
        rows = (
            db.session.query(
                month_expr.label("month"),
                func.coalesce(func.sum(amount_expr), 0).label("revenue"),
            )
            .filter(
                sale_model.project == division,
                sale_model.commercial_id == commercial_id,
            )
            .group_by(month_expr)
            .order_by(month_expr)
            .all()
        )
        for month, revenue in rows:
            if month is not None:
                combined.setdefault(str(month)[:7], 0.0)
                combined[str(month)[:7]] += float(revenue or 0)
    return sorted(combined.items())


def _commercial_revenue_detail(commercial_id, division, month):
    """Retourne le détail produit du CA du commercial pour un mois."""
    try:
        parsed = datetime.strptime(month, "%Y-%m")
    except ValueError:
        return None
    start = date(parsed.year, parsed.month, 1)
    end = date(parsed.year + 1, 1, 1) if parsed.month == 12 else date(parsed.year, parsed.month + 1, 1)
    rows = []
    for slug in DIVISION_SUPPLIERS.get(division, []):
        supplier = SUPPLIERS[slug]
        sale_model = supplier["sale_model"]
        product_model = supplier["product_model"]
        amount_expr = func.coalesce(sale_model.quantity, 0) * func.coalesce(sale_model.price, 0)
        query_rows = (
            db.session.query(
                product_model.name,
                func.coalesce(func.sum(sale_model.quantity), 0).label("quantity"),
                func.coalesce(func.sum(amount_expr), 0).label("revenue"),
            )
            .join(sale_model, sale_model.product_id == product_model.id)
            .filter(
                sale_model.project == division,
                sale_model.commercial_id == commercial_id,
                sale_model.date >= start,
                sale_model.date < end,
            )
            .group_by(product_model.id, product_model.name)
            .order_by(product_model.name.asc())
            .all()
        )
        for product_name, quantity, revenue in query_rows:
            rows.append(
                {
                    "supplier": supplier["label"],
                    "product": product_name,
                    "quantity": int(quantity or 0),
                    "revenue": float(revenue or 0),
                }
            )
    rows.sort(key=lambda row: (-row["revenue"], row["supplier"], row["product"]))
    return rows


@vm_cockpit_bp.route("/dashboard/vm", methods=["GET"])
@login_required
@roles_required("commercial")
def index():
    today = date.today()
    week_end = today + timedelta(days=7)
    visits_today = _unique_visit_rows_for_commercial(current_user.id, date_filter=today)
    upcoming = Client.query.filter(
        Client.owner_id == current_user.id,
        Client.next_visit.isnot(None),
        Client.next_visit >= today,
        Client.next_visit <= week_end,
    ).order_by(Client.next_visit.asc()).all()
    overdue = Client.query.filter(
        Client.owner_id == current_user.id,
        Client.next_visit.isnot(None),
        Client.next_visit < today,
    ).order_by(Client.next_visit.asc()).all()
    recent = _unique_visit_rows_for_commercial(current_user.id, limit=10)

    presented = Counter()
    prescribed = Counter()
    for visit in recent:
        for product in (visit.products_presented or "").split(","):
            if product.strip():
                presented[product.strip()] += 1
        for product in (visit.products_prescribed or "").split(","):
            if product.strip():
                prescribed[product.strip()] += 1

    visit_kpi = unique_visit_count_for_commercial(current_user.id)
    return render_template(
        "vm_cockpit.html",
        today=today,
        visits_today=visits_today,
        visits_week=upcoming,
        upcoming=upcoming,
        overdue=overdue,
        recent=recent,
        presented=presented.most_common(5),
        prescribed=prescribed.most_common(5),
        visit_kpi=visit_kpi,
    )


@vm_cockpit_bp.route("/commercial_dashboard/<username>/revenue-data", methods=["GET"])
@login_required
@roles_required("admin", "commercial")
def commercial_revenue_data(username):
    """API dédiée à la fiche commerciale : CA uniquement de sa division."""
    commercial = User.query.filter_by(username=username, role="commercial").first_or_404()
    if current_user.role == "commercial" and current_user.id != commercial.id:
        return jsonify({"error": "Accès non autorisé."}), 403

    division = (commercial.project or "").lower()
    if division not in DIVISION_SUPPLIERS:
        return jsonify({"commercial": commercial.username, "division": division, "months": [], "total": 0.0})

    months = _commercial_revenue(commercial.id, division)
    return jsonify(
        {
            "commercial": commercial.username,
            "division": division,
            "division_label": division.upper(),
            "months": [
                {"month": month, "revenue": round(revenue, 2)}
                for month, revenue in months
            ],
            "total": round(sum(revenue for _, revenue in months), 2),
        }
    )


@vm_cockpit_bp.route("/commercial_dashboard/<username>/revenue-detail/<month>", methods=["GET"])
@login_required
@roles_required("admin", "commercial")
def commercial_revenue_detail(username, month):
    """API du détail produit pour un mois donné, limité au commercial."""
    commercial = User.query.filter_by(username=username, role="commercial").first_or_404()
    if current_user.role == "commercial" and current_user.id != commercial.id:
        return jsonify({"error": "Accès non autorisé."}), 403

    division = (commercial.project or "").lower()
    if division not in DIVISION_SUPPLIERS:
        return jsonify({"commercial": commercial.username, "division": division, "month": month, "rows": [], "total": 0.0})

    rows = _commercial_revenue_detail(commercial.id, division, month)
    return jsonify(
        {
            "commercial": commercial.username,
            "division": division,
            "month": month,
            "rows": rows,
            "total": round(sum(row["revenue"] for row in rows), 2),
        }
    )
