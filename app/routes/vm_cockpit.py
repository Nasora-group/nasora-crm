from datetime import date, timedelta
from collections import Counter
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models_clients import Client, ClientVisit
from app.models import SUPPLIERS, DIVISION_SUPPLIERS, SalesObjective
from app.utils import roles_required
from app.extensions import db

vm_cockpit_bp = Blueprint("vm_cockpit", __name__)


def _commercial_revenue_kpis(commercial):
    """Affiche au commercial le même CA de division que celui visible par l'admin.
    Le CA n'est donc PAS limité aux ventes saisies par le commercial connecté.
    Un commercial NASMEDIC voit le CA NASMEDIC; un commercial NASDERM voit le CA NASDERM.
    """
    today = date.today()
    division = commercial.project
    month_key = today.strftime("%Y-%m")
    current_year = today.year
    monthly_revenue = 0
    annual_revenue = 0

    # Même logique que le tableau de CA admin : toutes les ventes de la division.
    for slug in DIVISION_SUPPLIERS.get(division, []):
        sale_model = SUPPLIERS[slug]["sale_model"]
        rows = db.session.query(sale_model.date, sale_model.quantity, sale_model.price).filter(
            sale_model.project == division,
        ).all()
        for sale_date, quantity, price in rows:
            amount = (quantity or 0) * (price or 0)
            if sale_date.strftime("%Y-%m") == month_key:
                monthly_revenue += amount
            if sale_date.year == current_year:
                annual_revenue += amount

    monthly_objective = SalesObjective.query.filter_by(
        division=division, year=current_year, month=today.month
    ).first()
    annual_objective = SalesObjective.query.filter_by(
        division=division, year=current_year, month=None
    ).first()
    monthly_target = monthly_objective.target_amount if monthly_objective else None
    annual_target = annual_objective.target_amount if annual_objective else None

    return {
        "division": division,
        "division_label": division.upper(),
        "monthly_revenue": monthly_revenue,
        "annual_revenue": annual_revenue,
        "monthly_target": monthly_target,
        "annual_target": annual_target,
        "monthly_pct": (monthly_revenue / monthly_target * 100) if monthly_target else None,
        "annual_pct": (annual_revenue / annual_target * 100) if annual_target else None,
        "current_year": current_year,
    }


@vm_cockpit_bp.route("/dashboard/vm", methods=["GET"])
@login_required
@roles_required("commercial")
def index():
    today = date.today()
    week_end = today + timedelta(days=7)
    visits_today = ClientVisit.query.filter_by(commercial_id=current_user.id, date=today).order_by(ClientVisit.id.desc()).all()
    upcoming = Client.query.filter(Client.owner_id == current_user.id, Client.next_visit.isnot(None), Client.next_visit >= today, Client.next_visit <= week_end).order_by(Client.next_visit.asc()).all()
    overdue = Client.query.filter(Client.owner_id == current_user.id, Client.next_visit.isnot(None), Client.next_visit < today).order_by(Client.next_visit.asc()).all()
    recent = ClientVisit.query.filter_by(commercial_id=current_user.id).order_by(ClientVisit.date.desc(), ClientVisit.id.desc()).limit(10).all()
    presented = Counter(); prescribed = Counter()
    for visit in recent:
        for product in (visit.products_presented or "").split(","):
            if product.strip(): presented[product.strip()] += 1
        for product in (visit.products_prescribed or "").split(","):
            if product.strip(): prescribed[product.strip()] += 1

    revenue_kpis = _commercial_revenue_kpis(current_user)
    return render_template("vm_cockpit.html", today=today, visits_today=visits_today, visits_week=upcoming, upcoming=upcoming, overdue=overdue, recent=recent, presented=presented.most_common(5), prescribed=prescribed.most_common(5), revenue_kpis=revenue_kpis)
