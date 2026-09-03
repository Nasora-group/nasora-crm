"""Lightweight audit logging for sensitive SaaS actions.

This module deliberately uses the application logger instead of introducing a
new database table or migration. It is safe to enable in production without
changing existing data.
"""
import logging

from flask_login import current_user

logger = logging.getLogger("nasora.audit")


def audit(action, *, target=None, outcome="success", details=None):
    """Write a structured, non-sensitive audit event to the application log."""
    actor = getattr(current_user, "username", None) or "anonymous"
    role = getattr(current_user, "role", None) or "unknown"
    division = getattr(current_user, "project", None) or "unknown"
    target_value = str(target) if target is not None else "-"
    safe_details = str(details) if details is not None else "-"
    logger.info(
        "AUDIT action=%s actor=%s role=%s division=%s target=%s outcome=%s details=%s",
        action,
        actor,
        role,
        division,
        target_value,
        outcome,
        safe_details,
    )
