import logging

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.forms import UserForm, CSRFOnlyForm
from app.models import User
from app.utils import roles_required
from app.audit_log import audit

logger = logging.getLogger(__name__)

users_bp = Blueprint("users", __name__, url_prefix="/admin/utilisateurs")


def _would_remove_last_admin(user, new_role=None, new_active=None):
    """Empêche de laisser l'application sans administrateur actif."""
    role = user.role if new_role is None else new_role
    active = user.is_active_account if new_active is None else new_active
    if role == "admin" and active:
        return False
    if user.role != "admin" or not user.is_active_account:
        return False
    return User.query.filter(
        User.role == "admin",
        User.is_active_account.is_(True),
        User.id != user.id,
    ).count() == 0


@users_bp.route("/")
@login_required
@roles_required("admin")
def list_users():
    role_filter = request.args.get("role", "")
    division_filter = request.args.get("project", "")

    query = User.query
    if role_filter:
        query = query.filter_by(role=role_filter)
    if division_filter:
        query = query.filter_by(project=division_filter)

    all_users = query.order_by(User.role.desc(), User.project, User.username).all()
    toggle_form = CSRFOnlyForm()
    return render_template("admin_users.html", users=all_users, toggle_form=toggle_form)


@users_bp.route("/nouveau", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_user():
    form = UserForm()

    if form.validate_on_submit():
        existing = User.query.filter_by(username=form.username.data.strip()).first()
        if existing:
            flash("Ce nom d'utilisateur existe déjà.", "error")
        elif not form.password.data:
            flash("Le mot de passe est obligatoire à la création d'un compte.", "error")
        else:
            try:
                user = User(
                    username=form.username.data.strip(),
                    password=generate_password_hash(form.password.data, method="pbkdf2:sha256"),
                    role=form.role.data,
                    project=form.project.data,
                    zone=form.zone.data or None,
                    is_active_account=form.is_active_account.data,
                )
                db.session.add(user)
                db.session.commit()
                flash(f"Compte « {user.username} » créé avec succès.", "success")
                audit(
                    "admin.user.create",
                    target=user.username,
                    details=f"role={user.role} project={user.project} active={user.is_active_account}",
                )
                logger.info("Compte créé par %s : %s (%s/%s)", current_user.username, user.username, user.role, user.project)
                return redirect(url_for("users.list_users"))
            except Exception:
                db.session.rollback()
                logger.exception("Erreur lors de la création du compte")
                flash("Erreur lors de la création du compte.", "error")

    return render_template("admin_user_form.html", form=form, mode="create", user=None)


@users_bp.route("/<int:user_id>/modifier", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)

    if request.method == "GET":
        form.password.data = ""

    if form.validate_on_submit():
        new_username = form.username.data.strip()
        existing = User.query.filter(User.username == new_username, User.id != user.id).first()

        if existing:
            flash("Ce nom d'utilisateur est déjà utilisé par un autre compte.", "error")
        elif user.id == current_user.id and not form.is_active_account.data:
            flash("Tu ne peux pas désactiver ton propre compte.", "error")
        elif user.id == current_user.id and form.role.data != "admin":
            flash("Tu ne peux pas retirer ton propre rôle administrateur.", "error")
        elif _would_remove_last_admin(user, new_role=form.role.data, new_active=form.is_active_account.data):
            flash("Impossible de retirer ou désactiver le dernier administrateur actif.", "error")
        else:
            try:
                old_username = user.username
                old_role = user.role
                old_project = user.project
                old_zone = user.zone
                old_active = user.is_active_account
                password_changed = bool(form.password.data)

                user.username = new_username
                user.role = form.role.data
                user.project = form.project.data
                user.zone = form.zone.data or None
                user.is_active_account = form.is_active_account.data
                if password_changed:
                    user.password = generate_password_hash(form.password.data, method="pbkdf2:sha256")
                db.session.commit()
                flash(f"Compte « {user.username} » mis à jour.", "success")

                changes = []
                if old_username != user.username:
                    changes.append("username")
                if old_role != user.role:
                    changes.append(f"role:{old_role}->{user.role}")
                if old_project != user.project:
                    changes.append(f"project:{old_project}->{user.project}")
                if old_zone != user.zone:
                    changes.append("zone")
                if old_active != user.is_active_account:
                    changes.append(f"active:{old_active}->{user.is_active_account}")
                if password_changed:
                    changes.append("password_changed")

                audit(
                    "admin.user.update",
                    target=user.username,
                    details=f"changes={','.join(changes) if changes else 'none'}",
                )
                logger.info("Compte modifié par %s : %s", current_user.username, user.username)
                return redirect(url_for("users.list_users"))
            except Exception:
                db.session.rollback()
                logger.exception("Erreur lors de la modification du compte")
                flash("Erreur lors de la mise à jour du compte.", "error")

    return render_template("admin_user_form.html", form=form, mode="edit", user=user)


@users_bp.route("/<int:user_id>/basculer-statut", methods=["POST"])
@login_required
@roles_required("admin")
def toggle_active(user_id):
    form = CSRFOnlyForm()
    if not form.validate_on_submit():
        flash("Requête invalide.", "error")
        return redirect(url_for("users.list_users"))

    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("Tu ne peux pas désactiver ton propre compte.", "error")
        return redirect(url_for("users.list_users"))

    if _would_remove_last_admin(user, new_active=not user.is_active_account):
        flash("Impossible de désactiver le dernier administrateur actif.", "error")
        return redirect(url_for("users.list_users"))

    user.is_active_account = not user.is_active_account
    db.session.commit()
    etat = "activé" if user.is_active_account else "désactivé"
    flash(f"Compte « {user.username} » {etat}.", "success")
    audit(
        "admin.user.status",
        target=user.username,
        details=f"active={user.is_active_account}",
    )
    logger.info("Compte %s %s par %s", user.username, etat, current_user.username)
    return redirect(url_for("users.list_users"))
