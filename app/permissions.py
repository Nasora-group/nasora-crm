"""Centralized authorization primitives for NASORA CRM.

This module deliberately contains no database writes and no migration logic.
It provides one place for route-level role, ownership and division checks so
future SaaS tenant isolation can be strengthened without changing business
rules or production data.
"""

from functools import wraps

from flask import abort, flash, redirect, url_for
from flask_login import current_user


ADMIN_ROLE = "admin"
COMMERCIAL_ROLE = "commercial"


def normalized_role(user=None):
    """Return the normalized role of a user, or an empty string."""
    user = user or current_user
    return (getattr(user, "role", "") or "").strip().lower()


def normalized_division(user=None):
    """Return the normalized division/project of a user."""
    user = user or current_user
    return (getattr(user, "project", "") or "").strip().lower()


def is_admin(user=None):
    return normalized_role(user) == ADMIN_ROLE


def is_commercial(user=None):
    return normalized_role(user) == COMMERCIAL_ROLE


def account_is_active(user=None):
    user = user or current_user
    return bool(user and getattr(user, "is_authenticated", False) and getattr(user, "is_active_account", False))


def has_role(*roles):
    """Return whether the current user has one of the supplied roles."""
    allowed = {str(role).strip().lower() for role in roles if str(role).strip()}
    return account_is_active() and normalized_role() in allowed


def division_matches(user, division):
    """Admins can cross divisions; commercial users are division-scoped."""
    if not account_is_active(user):
        return False
    if is_admin(user):
        return True
    target = (division or "").strip().lower()
    return bool(target and normalized_division(user) == target)


def owns_record(user, record, owner_field="commercial_id"):
    """Return True when a record belongs to the authenticated user.

    Admins may access records across users. Commercial users may only access
    records whose configured owner field matches their own user id.
    """
    if not account_is_active(user) or record is None:
        return False
    if is_admin(user):
        return True
    return getattr(record, owner_field, None) == getattr(user, "id", None)


def authorize_role(*roles):
    """Decorator for routes requiring authentication and one of the roles."""
    allowed = {str(role).strip().lower() for role in roles if str(role).strip()}

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not getattr(current_user, "is_authenticated", False):
                return redirect(url_for("auth.login"))
            if not getattr(current_user, "is_active_account", False):
                flash("Votre compte est désactivé. Contactez un administrateur.", "error")
                return redirect(url_for("auth.login"))
            if normalized_role() not in allowed:
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


def require_owner(record, owner_field="commercial_id"):
    """Abort with 403 unless the current user may access the record."""
    if not owns_record(current_user, record, owner_field=owner_field):
        abort(403)
    return record


def require_division(division, user=None):
    """Abort with 403 unless the user may access the requested division."""
    if not division_matches(user or current_user, division):
        abort(403)
    return True
