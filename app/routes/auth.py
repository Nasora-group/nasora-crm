import logging

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

from app.forms import LoginForm
from app.models import User

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def home():
    return render_template("welcome.html")


@auth_bp.route("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="images/logo.jpg"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard") if current_user.role == "admin" else url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data
        user = User.query.filter_by(username=username).first()

        if user and user.is_active_account and check_password_hash(user.password, password):
            login_user(user)
            logger.info("Connexion réussie pour %s", username)
            if user.role == "admin":
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("dashboard.index"))

        flash("Nom d'utilisateur ou mot de passe incorrect", "error")
        logger.warning("Tentative de connexion échouée pour '%s'", username)

    return render_template("login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Déconnexion réussie", "success")
    return redirect(url_for("auth.home"))
