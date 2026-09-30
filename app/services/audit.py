import json
import logging
import os
from datetime import datetime, timezone
from flask import request
from flask_login import current_user
from sqlalchemy import insert
from app.extensions import db
from app.models_audit import AuditLog

logger = logging.getLogger("nasora.audit")


def get_audit_tenant_id():
    """Return the configured audit tenant identifier for the current deployment."""
    raw = os.environ.get("AUDIT_TENANT_ID", "116").strip()
    try:
        tenant_id = int(raw)
    except (TypeError, ValueError):
        tenant_id = 116
    return tenant_id if tenant_id > 0 else 116


def audit_event(action, entity, entity_id=None, details=None, actor=None):
    """Persist a structured business audit event in its own transaction."""
    actor = actor or (current_user if current_user.is_authenticated else None)
    details = details or {}
    timestamp = datetime.now(timezone.utc)
    tenant_id = get_audit_tenant_id()
    payload = {
        "timestamp": timestamp.isoformat(),
        "action": str(action),
        "entity": str(entity),
        "entity_id": entity_id,
        "actor_id": getattr(actor, "id", None),
        "actor": getattr(actor, "username", None),
        "role": getattr(actor, "role", None),
        "division": getattr(actor, "project", None),
        "method": request.method if request else None,
        "path": request.path if request else None,
        "details": details,
    }
    logger.info("AUDIT %s", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    try:
        values = {
            "tenant_id": tenant_id,
            "actor_user_id": getattr(actor, "id", None),
            "action": str(action),
            "entity_type": str(entity),
            "entity_id": str(entity_id) if entity_id is not None else None,
            "details": payload,
            "ip_address": (request.headers.get("X-Forwarded-For", request.remote_addr) if request else None),
            "user_agent": (request.user_agent.string[:500] if request else None),
            "created_at": timestamp,
        }
        with db.engine.begin() as connection:
            connection.execute(insert(AuditLog.__table__).values(**values))
    except Exception:
        logger.exception("Impossible de persister l'événement d'audit")
    return payload
