from flask import url_for
from app.extensions import db
from app.models import AdminNotification, User


def notify_admins(actor, event_type, title, message, endpoint, **endpoint_values):
    """Ajoute une notification pour chaque administrateur actif dans la même transaction."""
    if not actor or actor.role == "admin":
        return
    try:
        target_url = url_for(endpoint, **endpoint_values)
    except Exception:
        target_url = url_for("admin_notifications.index")
    admins = User.query.filter_by(role="admin", is_active_account=True).all()
    for admin in admins:
        db.session.add(AdminNotification(
            admin_id=admin.id,
            actor_id=actor.id,
            event_type=event_type,
            title=title,
            message=message,
            target_url=target_url,
        ))
