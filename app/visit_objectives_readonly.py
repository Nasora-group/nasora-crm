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


def install_readonly_objective_reader():
    """Replace the legacy dashboard helper with the strictly read-only one."""
    from app.routes import dashboard

    dashboard._visit_targets_for_commercials = read_visit_targets
