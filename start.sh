#!/usr/bin/env bash
# Render Start Command: bash start.sh
# Les migrations et le seed sont exécutés avant Gunicorn, une seule fois.
set -euo pipefail

echo "[start.sh] Vérification de la configuration..."
if [[ "${FLASK_ENV:-}" == "production" && -z "${DATABASE_URL:-}" ]]; then
  echo "[start.sh] ERREUR: DATABASE_URL est obligatoire en production."
  exit 1
fi
if [[ "${FLASK_ENV:-}" == "production" && -z "${SECRET_KEY:-}" ]]; then
  echo "[start.sh] ERREUR: SECRET_KEY est obligatoire en production."
  exit 1
fi

echo "[start.sh] Application des migrations..."
flask db upgrade

echo "[start.sh] Vérification/création des comptes et du catalogue produit..."
python seed.py

echo "[start.sh] Démarrage de gunicorn..."
exec gunicorn wsgi:app --workers 2 --threads 4 --timeout 60
