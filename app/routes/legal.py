from flask import Blueprint, render_template

legal_bp = Blueprint("legal", __name__)


@legal_bp.get("/rgpd")
def rgpd():
    return render_template("rgpd.html")


@legal_bp.get("/cgu")
def cgu():
    return render_template("cgu.html")
