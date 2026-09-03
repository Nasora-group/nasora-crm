"""Read-only access to per-commercial visit objectives.

The Activity Terrain dashboard is a GET endpoint and must never create or
modify database schema. The existing POST endpoint in routes.visit_targets is
responsible for creating the table when an administrator explicitly saves an
objective.
"""

import logging

from sqlalchemy import bindparam, text

from app.extensions import db

logger = logging.getLogger(__name__)


def read_visit_targets(commercials):
    """Return configured targets without ever creating or committing schema."""
    targets = {commercial.id: 100 for commercial in commercials}
    if not commercials:
        return targets

    try:
        statement = text(
            "SELECT commercial_id, target "
            "FROM visit_objective "
            "WHERE commercial_id IN :ids"
        ).bindparams(bindparam("ids", expanding=True))
        rows = db.session.execute(
            statement,
            {"ids": [commercial.id for commercial in commercials]},
        ).mappings().all()
        for row in rows:
            targets[int(row["commercial_id"])] = int(row["target"])
    except Exception:
        # Older databases may not have the optional table yet. A dashboard GET
        # must remain usable and must not create it as a side effect.
        db.session.rollback()
        logger.info(
            "Table visit_objective absente; utilisation des objectifs par défaut."
        )

    return targets


def read_visit_target(commercial_id):
    """Read one commercial's target without invoking the legacy write-on-read helper."""
    from app.models import User

    commercial = db.session.get(User, commercial_id)
    if not commercial or commercial.role != "commercial":
        return 100
    return int(read_visit_targets([commercial]).get(commercial_id, 100))


def install_readonly_objective_reader():
    """Replace legacy objective readers with strictly read-only implementations."""
    from app.routes import dashboard
    from app.routes import admin

    dashboard._visit_targets_for_commercials = read_visit_targets
    admin._visit_target_for_commercial = read_visit_target
