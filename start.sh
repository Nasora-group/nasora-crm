#!/usr/bin/env bash
# Script de démarrage utilisé par Render (Start Command = "bash start.sh").
# set -e : si une étape échoue, on arrête tout de suite plutôt que de démarrer
# le serveur avec une base de données pas à jour.
set -e

echo "[start.sh] Application des migrations..."
flask db upgrade

echo "[start.sh] Vérification/création des comptes et du catalogue produit..."
python seed.py

echo "[start.sh] Démarrage de gunicorn..."
exec gunicorn wsgi:app --workers 2 --threads 4 --timeout 60
