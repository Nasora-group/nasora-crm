import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import text

from app.extensions import db
from app.models import User
from app.utils import roles_required

logger = logging.getLogger(__name__)
visit_targets_bp = Blueprint("visit_targets", __name__, url_prefix="/admin/visit-objectives")


def _ensure_table():
    """Create the small per-commercial target table when it is missing.

    The repository currently has no active Alembic revision in migrations/versions,
    so this idempotent DDL keeps existing production databases compatible.
    """
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS visit_objective (
            commercial_id INTEGER PRIMARY KEY,
            target INTEGER NOT NULL DEFAULT 100 CHECK (target >= 0)
        )
    """))
    db.session.commit()


@visit_targets_bp.route("", methods=["GET"])
@login_required
@roles_required("admin")
def list_targets():
    _ensure_table()
    rows = db.session.execute(text("SELECT commercial_id, target FROM visit_objective")).mappings().all()
    values = {str(row["commercial_id"]): int(row["target"]) for row in rows}
    return jsonify(values)


@visit_targets_bp.route("/<int:commercial_id>", methods=["POST"])
@login_required
@roles_required("admin")
def update_target(commercial_id):
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
