import os
import logging
from flask import Flask, render_template, request
from flask_login import current_user
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
            raise RuntimeError("SECRET_KEY manquant : définis la variable d'environnement SECRET_KEY avant de lancer l'application en production.")
    _configure_logging(app)
    db.init_app(app); migrate.init_app(app, db); csrf.init_app(app); cache.init_app(app); login_manager.init_app(app)
    from app.models import User
    from app.models_stock import StockEntry  # noqa: F401
    @login_manager.user_loader
    def load_user(user_id):
        user = db.session.get(User, int(user_id))
        return user if user and user.is_active_account else None
    _register_blueprints(app)
    from app.visit_objectives_readonly import install_readonly_objective_reader
    install_readonly_objective_reader()
    from app import visit_sync  # noqa: F401
    _register_error_handlers(app)
    @app.after_request
    def apply_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(self), microphone=(), camera=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        if current_user.is_authenticated or request.path == "/login":
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
        if os.environ.get("FLASK_ENV", "").lower() == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
    @app.context_processor
    def inject_globals():
        from datetime import datetime, UTC
        from app.models import SUPPLIERS, STRUCTURE_COLORS
        active_slugs = [slug for slug, s in SUPPLIERS.items() if not s.get("archived")]
        return {"current_year": datetime.now(UTC).year, "first_active_supplier_slug": active_slugs[0] if active_slugs else None, "structure_colors": STRUCTURE_COLORS}
    from app.utils import format_planning_slot, planning_entries
    app.jinja_env.filters["planning_slot"] = format_planning_slot
    app.jinja_env.filters["planning_entries"] = planning_entries
    return app

def _configure_logging(app):
    level = logging.DEBUG if app.debug else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

def _register_blueprints(app):
    from app.routes.auth import auth_bp
    from app.routes.dashboard_direction_safe import terrain_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.planning import planning_bp
    from app.routes.sales import sales_bp
    from app.routes.revenue import revenue_bp
    from app.routes.admin import admin_bp
    from app.routes.users import users_bp
    from app.routes.products import products_bp
    from app.routes.objectives import objectives_bp
    from app.routes.evaluations import evaluations_bp
    from app.routes.commercial_evaluations import commercial_evaluations_bp
    from app.routes.clients import clients_bp
    from app.routes.clients_export import clients_export_bp
    from app.routes.prospections_export import prospections_export_bp
    from app.routes.vm_cockpit import vm_cockpit_bp
    from app.routes.stock import stock_bp
    from app.routes.visit_targets import visit_targets_bp
    app.register_blueprint(auth_bp); app.register_blueprint(terrain_bp); app.register_blueprint(dashboard_bp); app.register_blueprint(planning_bp); app.register_blueprint(sales_bp); app.register_blueprint(revenue_bp); app.register_blueprint(admin_bp); app.register_blueprint(users_bp); app.register_blueprint(products_bp); app.register_blueprint(objectives_bp); app.register_blueprint(evaluations_bp); app.register_blueprint(commercial_evaluations_bp); app.register_blueprint(clients_bp); app.register_blueprint(clients_export_bp); app.register_blueprint(prospections_export_bp); app.register_blueprint(vm_cockpit_bp); app.register_blueprint(stock_bp); app.register_blueprint(visit_targets_bp)

def _register_error_handlers(app):
    @app.errorhandler(404)
    def page_not_found(e): return render_template("404.html"), 404
    @app.errorhandler(500)
    def internal_server_error(e): db.session.rollback(); return render_template("500.html"), 500
    @app.errorhandler(403)
    def forbidden(e): return render_template("403.html"), 403
