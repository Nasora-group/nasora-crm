import os

from sqlalchemy import text
from flask_migrate import upgrade

from app import create_app

app = create_app()


def _run_render_migrations():
    """Apply pending Alembic migrations once before serving traffic on Render."""
    if os.environ.get("RENDER", "").lower() != "true":
        return

    # Gunicorn may import this module in multiple worker processes. The
    # advisory lock serializes migration execution across those workers.
    lock_key = 846217391
    with app.app_context():
        conn = app.extensions["migrate"].db.engine.connect()
        try:
            conn.execute(text("SELECT pg_advisory_lock(:lock_key)"), {"lock_key": lock_key})
            upgrade()
        finally:
            try:
                conn.execute(text("SELECT pg_advisory_unlock(:lock_key)"), {"lock_key": lock_key})
            finally:
                conn.close()


_run_render_migrations()

if __name__ == "__main__":
    app.run()
