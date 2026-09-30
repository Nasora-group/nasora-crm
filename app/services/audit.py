import json
import logging
from datetime import datetime, timezone
from flask import request
from flask_login import current_user

logger = logging.getLogger("nasora.audit")


def audit_event(action, entity, entity_id=None, details=None, actor=None):
    """Journalise une action métier réussie dans les logs applicatifs.

    Le projet conserve volontairement l'audit comme journal applicatif:
    aucune nouvelle table ni migration n'est nécessaire.
    """
    actor = actor or (current_user if current_user.is_authenticated else None)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": str(action),
        "entity": str(entity),
        "entity_id": entity_id,
        "actor_id": getattr(actor, "id", None),
        "actor": getattr(actor, "username", None),
        "role": getattr(actor, "role", None),
        "division": getattr(actor, "project", None),
        "method": request.method if request else None,
        "path": request.path if request else None,
        "details": details or {},
    }
    logger.info("AUDIT %s", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return payload
