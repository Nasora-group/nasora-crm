"""Point d'entrée pour le développement local : python run.py"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", False), host="127.0.0.1", port=5000)
