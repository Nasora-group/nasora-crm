web: gunicorn wsgi:app --workers 2 --threads 4 --timeout 60
release: flask db upgrade && python seed.py
