from flask import Blueprint, redirect, render_template, url_for, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models import AdminNotification
from app.utils import roles_required

admin_notifications_bp = Blueprint("admin_notifications", __name__, url_prefix="/admin/notifications")


@admin_notifications_bp.route("")
@login_required
@roles_required("admin")
def index():
    notifications = (
        AdminNotification.query
        .filter_by(admin_id=current_user.id)
        .order_by(AdminNotification.created_at.desc(), AdminNotification.id.desc())
        .limit(100)
        .all()
    )
    return render_template("admin_notifications.html", notifications=notifications)


@admin_notifications_bp.route("/<int:notification_id>/ouvrir")
@login_required
@roles_required("admin")
def open_notification(notification_id):
    notification = AdminNotification.query.filter_by(
        id=notification_id, admin_id=current_user.id
    ).first_or_404()
    notification.is_read = True
    db.session.commit()
    target = notification.target_url or url_for("admin_notifications.index")
    return redirect(target)


@admin_notifications_bp.route("/lire-tout", methods=["POST"])
@login_required
@roles_required("admin")
def mark_all_read():
    AdminNotification.query.filter_by(admin_id=current_user.id, is_read=False).update(
        {AdminNotification.is_read: True}, synchronize_session=False
    )
    db.session.commit()
    return redirect(request.referrer or url_for("admin_notifications.index"))
