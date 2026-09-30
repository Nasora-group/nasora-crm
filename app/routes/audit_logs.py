import json
import logging
from pathlib import Path

from flask import Blueprint, render_template, request
from flask_login import login_required

from app.utils import roles_required

audit_bp = Blueprint("audit", __name__, url_prefix="/admin/audit")
logger = logging.getLogger("nasora.audit")


@audit_bp.route("")
@login_required
@roles_required("admin")
def index():
    """Affiche les derniers événements d'audit disponibles dans le journal applicatif."""
    limit = min(max(request.args.get("limit", 100, type=int), 20), 300)
    records = []
    for handler in logger.handlers:
        filename = getattr(handler, "baseFilename", None)
        if not filename:
            continue
        try:
            lines = Path(filename).read_text(encoding="utf-8").splitlines()[-limit:]
        except (OSError, UnicodeDecodeError):
            continue
        for line in reversed(lines):
            marker = "AUDIT "
            if marker not in line:
                continue
            raw = line.split(marker, 1)[1].strip()
            try:
                records.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
            if len(records) >= limit:
                break
        if records:
            break
    return render_template("audit_logs.html", records=records, limit=limit)
