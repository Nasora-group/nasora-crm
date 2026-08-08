import os
import logging

from flask import Flask, render_template
from dotenv import load_dotenv

from app.config import get_config
from app.extensions import db, login_manager, migrate, csrf, cache

load_dotenv()


def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=True)

    config_object = config_object or get_config()
    app.config.from_object(config_object)

    os.makedirs(app.instance_path, exist_ok=True)

    if app.config.get("ENV") == "production" or os.environ.get("FLASK_ENV") == "production":
        if not os.environ.get("SECRET_KEY"):
            raise RuntimeError(
                "SECRET_KEY manquant : définis la variable d'environnement SECRET_KEY avant "
                "de lancer l'application en production."
            )

    _configure_logging(app)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    cache.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    _register_blueprints(app)
    _register_error_handlers(app)

    @app.context_processor
    def inject_globals():
        from datetime import datetime
        return {"current_year": datetime.utcnow().year}

    from app.utils import format_planning_slot
    app.jinja_env.filters["planning_slot"] = format_planning_slot

    return app


def _configure_logging(app):
    level = logging.DEBUG if app.debug else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _register_blueprints(app):
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.planning import planning_bp
    from app.routes.sales import sales_bp
    from app.routes.revenue import revenue_bp
    from app.routes.admin import admin_bp
    from app.routes.users import users_bp
    from app.routes.products import products_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(planning_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(revenue_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(products_bp)


def _register_error_handlers(app):
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        db.session.rollback()
        return render_template("500.html"), 500

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403
