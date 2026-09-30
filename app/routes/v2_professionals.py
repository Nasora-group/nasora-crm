from datetime import date, timedelta

from flask import Blueprint, render_template, request, abort
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models import User
from app.models_clients import Client, ClientVisit
from app.permissions import is_admin
from app.utils import roles_required

v2_professionals_bp = Blueprint("v2_professionals", __name__, url_prefix="/v2/professionnels")


def _can_access(client):
    if is_admin():
        return True
    return client.owner_id == current_user.id


@v2_professionals_bp.route("/")
@login_required
@roles_required("admin", "commercial")
def index():
    q = (request.args.get("q") or "").strip()
    zone = (request.args.get("zone") or "").strip()
    owner_id = request.args.get("owner_id", type=int)

    query = Client.query
    if not is_admin():
        query = query.filter(Client.owner_id == current_user.id)
    elif owner_id:
        query = query.filter(Client.owner_id == owner_id)
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Client.name.ilike(like),
                Client.structure.ilike(like),
                Client.establishment.ilike(like),
                Client.phone.ilike(like),
            )
        )
    if zone:
        query = query.filter(Client.zone.ilike(zone))
    clients = query.order_by(Client.name.asc()).limit(200).all()

    owners = User.query.filter_by(role="commercial").order_by(User.username.asc()).all() if is_admin() else []
    zones = [
        row[0] for row in db.session.query(Client.zone)
        .filter(Client.zone.isnot(None), Client.zone != "")
        .distinct().order_by(Client.zone.asc()).all()
    ]
    return render_template(
        "v2/professionals.html",
        clients=clients,
        owners=owners,
        zones=zones,
        q=q,
        zone=zone,
        owner_id=owner_id,
    )


@v2_professionals_bp.route("/<int:client_id>")
@login_required
@roles_required("admin", "commercial")
def detail(client_id):
    client = Client.query.get_or_404(client_id)
    if not _can_access(client):
        abort(403)

    visits = (
        ClientVisit.query
        .filter_by(client_id=client.id, is_duplicate=False)
        .order_by(ClientVisit.date.desc(), ClientVisit.id.desc())
        .all()
    )
    presented = set()
    prescribed = set()
    for visit in visits:
        for item in (visit.products_presented or "").split(","):
            if item.strip():
                presented.add(item.strip())
        for item in (visit.products_prescribed or "").split(","):
            if item.strip():
                prescribed.add(item.strip())

    last_90 = date.today() - timedelta(days=90)
    visits_90 = sum(1 for visit in visits if visit.date >= last_90)
    next_followups = sum(
        1 for visit in visits
        if visit.next_visit and visit.next_visit >= date.today()
    )
    return render_template(
        "v2/professional_detail.html",
        client=client,
        visits=visits,
        presented=sorted(presented),
        prescribed=sorted(prescribed),
        visits_90=visits_90,
        next_followups=next_followups,
        today=date.today(),
    )
