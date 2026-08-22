from datetime import date, timedelta
from collections import Counter
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models import Prospection
from app.models_clients import Client, ClientVisit
from app.utils import roles_required

vm_cockpit_bp = Blueprint("vm_cockpit", __name__)

@vm_cockpit_bp.route("/dashboard/vm", methods=["GET"])
@login_required
@roles_required("commercial")
def index():
    today = date.today()
    week_end = today + timedelta(days=7)
    visits_today = ClientVisit.query.filter_by(commercial_id=current_user.id, date=today).order_by(ClientVisit.id.desc()).all()
    visits_week = ClientVisit.query.filter(ClientVisit.commercial_id == current_user.id, ClientVisit.date >= today, ClientVisit.date <= week_end).order_by(ClientVisit.date.asc()).all()
    upcoming = Client.query.filter(Client.owner_id == current_user.id, Client.next_visit.isnot(None), Client.next_visit >= today, Client.next_visit <= week_end).order_by(Client.next_visit.asc()).all()
    overdue = Client.query.filter(Client.owner_id == current_user.id, Client.next_visit.isnot(None), Client.next_visit < today).order_by(Client.next_visit.asc()).all()
    recent = ClientVisit.query.filter_by(commercial_id=current_user.id).order_by(ClientVisit.date.desc(), ClientVisit.id.desc()).limit(10).all()
    presented = Counter(); prescribed = Counter()
    for v in recent:
        for p in (v.products_presented or "").split(","):
            if p.strip(): presented[p.strip()] += 1
        for p in (v.products_prescribed or "").split(","):
            if p.strip(): prescribed[p.strip()] += 1
    return render_template("vm_cockpit.html", today=today, visits_today=visits_today, visits_week=visits_week, upcoming=upcoming, overdue=overdue, recent=recent, presented=presented.most_common(5), prescribed=prescribed.most_common(5))
