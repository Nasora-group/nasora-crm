import os
import fcntl

from flask import Flask
from flask_migrate import upgrade
from app import create_app


def _apply_migrations(app):
    """Applique les migrations avant le démarrage de Gunicorn.

    Render utilise actuellement Gunicorn directement comme Start Command,
    donc le hook release du Procfile n'est pas exécuté. Le verrou fichier
    évite que les deux workers lancés par Gunicorn exécutent la migration
    simultanément.
    """
    lock_path = "/tmp/nasora-migration.lock"
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        with app.app_context():
            upgrade()


app = create_app()
_apply_migrations(app)


if __name__ == "__main__":
    app.run()
