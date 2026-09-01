from datetime import date, timedelta
from collections import Counter
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models_clients import Client, ClientVisit
from app.utils import roles_required
from app.extensions import db
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
