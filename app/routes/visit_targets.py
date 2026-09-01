import logging

from flask import Blueprint, jsonify, request, render_template
from flask_login import current_user, login_required
from sqlalchemy import text

from app.extensions import db
from app.models import User

logger = logging.getLogger(__name__)
visit_targets_bp = Blueprint("visit_targets", __name__, url_prefix="/admin/visit-objectives")


def _ensure_table():
    """Create the small per-commercial target table only when a write is requested.

    Reads must remain strictly read-only so loading the dashboard never changes
    the database schema or transaction state.
    """
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS visit_objective (
            commercial_id INTEGER PRIMARY KEY,
            target INTEGER NOT NULL DEFAULT 100 CHECK (target >= 0)
        )
    """))
    db.session.commit()


def _admin_only():
    """Return a real 403 for authenticated non-admin users."""
    if not current_user.is_authenticated:
        return None
    if current_user.role != "admin":
        return render_template("403.html"), 403
    return None


@visit_targets_bp.route("", methods=["GET"])
@login_required
def list_targets():
    forbidden = _admin_only()
    if forbidden is not None:
        return forbidden

    try:
        rows = db.session.execute(
            text("SELECT commercial_id, target FROM visit_objective")
        ).mappings().all()
    except Exception:
        # The table may not exist yet on an older database. A read must not
        # create it; the dashboard already uses the same 100-visit fallback.
        db.session.rollback()
        logger.info("Table visit_objective absente; utilisation des objectifs par défaut.")
        return jsonify({})

    values = {str(row["commercial_id"]): int(row["target"]) for row in rows}
    return jsonify(values)


@visit_targets_bp.route("/<int:commercial_id>", methods=["POST"])
@login_required
def update_target(commercial_id):
    forbidden = _admin_only()
    if forbidden is not None:
        return forbidden

    commercial = User.query.filter_by(id=commercial_id, role="commercial").first()
    if commercial is None:
        return jsonify({"ok": False, "error": "Commercial introuvable."}), 404

    raw = request.form.get("target", "").strip()
    try:
        target = int(raw)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "L'objectif doit être un nombre entier."}), 400
    if target < 0 or target > 10000:
        return jsonify({"ok": False, "error": "L'objectif doit être compris entre 0 et 10 000 visites."}), 400

    try:
        _ensure_table()
        db.session.execute(
            text("""
                INSERT INTO visit_objective (commercial_id, target)
                VALUES (:commercial_id, :target)
                ON CONFLICT (commercial_id) DO UPDATE SET target = EXCLUDED.target
            """),
            {"commercial_id": commercial_id, "target": target},
        )
        db.session.commit()
        return jsonify({"ok": True, "commercial_id": commercial_id, "target": target})
    except Exception:
        db.session.rollback()
        logger.exception("Erreur lors de la mise à jour de l'objectif de visites pour %s", commercial_id)
        return jsonify({"ok": False, "error": "Impossible d'enregistrer l'objectif."}), 500
