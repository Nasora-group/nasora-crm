import logging
from collections import Counter
from datetime import date

from flask import Blueprint, render_template, request
from flask_login import login_required

from sqlalchemy.orm import load_only

from app.models import Prospection, User
from app.utils import roles_required
from app.visit_metrics import professional_key
from app.routes.dashboard import _normalize_text
from app.visit_objectives_readonly import read_visit_targets

logger = logging.getLogger(__name__)
terrain_bp = Blueprint("dashboard_safe", __name__)


@terrain_bp.route("/admin/dashboard-direction", methods=["GET"])
@login_required
@roles_required("admin")
def direction():
    # La route historique reste disponible, mais le tableau Direction officiel
    # est désormais celui de dashboard.py (V3.4/V3.5).
    from app.routes.dashboard import direction as dashboard_direction
    return dashboard_direction()
