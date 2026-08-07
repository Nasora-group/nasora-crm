import logging

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.forms import UserForm, CSRFOnlyForm
from app.models import User
from app.utils import roles_required

logger = logging.getLogger(__name__)

users_bp = Blueprint("users", __name__, url_prefix="/admin/utilisateurs")


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
        else:
            try:
                user.username = new_username
                user.role = form.role.data
                user.project = form.project.data
                user.zone = form.zone.data or None
                user.is_active_account = form.is_active_account.data
                if form.password.data:
                    user.password = generate_password_hash(form.password.data, method="pbkdf2:sha256")
                db.session.commit()
                flash(f"Compte « {user.username} » mis à jour.", "success")
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

    user.is_active_account = not user.is_active_account
    db.session.commit()
    etat = "activé" if user.is_active_account else "désactivé"
    flash(f"Compte « {user.username} » {etat}.", "success")
    logger.info("Compte %s %s par %s", user.username, etat, current_user.username)
    return redirect(url_for("users.list_users"))
