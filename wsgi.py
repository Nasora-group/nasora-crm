from app import create_app

# Les migrations et le seed sont exécutés une seule fois par le processus
# de release/startup Render (start.sh). Le serveur web ne doit pas modifier
# le schéma PostgreSQL pendant l'import du module, notamment avec plusieurs
# workers Gunicorn.
app = create_app()


if __name__ == "__main__":
    app.run()
