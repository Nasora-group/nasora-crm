from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
from flask_caching import Cache

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()
cache = Cache()

login_manager.login_view = "auth.login"
login_manager.login_message = "Merci de vous connecter pour accéder à cette page."
login_manager.login_message_category = "info"
# Détecte les changements d'identité/session et invalide une session suspecte.
login_manager.session_protection = "strong"
