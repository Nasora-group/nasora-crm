from flask import Blueprint, render_template, request
from flask_login import login_required

from app.extensions import db
from app.models_audit import AuditLog
from app.utils import roles_required
from app.services.audit import get_audit_tenant_id

audit_bp = Blueprint("audit", __name__, url_prefix="/admin/audit")


@audit_bp.route("")
@login_required
@roles_required("admin")
def index():
    """Affiche les derniers événements d'audit persistants."""
    limit = min(max(request.args.get("limit", 100, type=int), 20), 300)
    tenant_id = get_audit_tenant_id()
    records = (
        AuditLog.query
        .filter(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return render_template("audit_logs.html", records=records, limit=limit)
