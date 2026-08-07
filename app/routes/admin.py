import logging
from io import BytesIO

import pandas as pd
from flask import Blueprint, render_template, request, send_file, flash, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.extensions import db
from app.forms import DownloadExcelForm
from app.models import (
    User, Prospection,
    NovaPharmaSale, GilbertSale, EricFavreSale, TroisCheneSale,
)
from app.utils import roles_required

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__)

SALE_MODELS = [NovaPharmaSale, GilbertSale, EricFavreSale, TroisCheneSale]


@admin_bp.route("/admin_dashboard", methods=["GET"])
@login_required
@roles_required("admin")
def dashboard():
    revenue_dict = {}
    for sale_model in SALE_MODELS:
        rows = db.session.query(sale_model.date, sale_model.quantity, sale_model.price).all()
        for sale_date, quantity, price in rows:
            month = sale_date.strftime("%Y-%m")
            revenue_dict.setdefault(month, 0)
            revenue_dict[month] += (quantity or 0) * (price or 0)

    monthly_revenue_labels = sorted(revenue_dict.keys())
    monthly_revenue_data = [revenue_dict[m] for m in monthly_revenue_labels]

    commerciaux = User.query.filter_by(role="commercial").order_by(User.username).all()
    top_5_commerciaux = (
        db.session.query(User.username, User.zone, func.count(Prospection.id).label("nombre_visites"))
        .join(Prospection)
        .group_by(User.id)
        .order_by(func.count(Prospection.id).desc())
        .limit(5)
        .all()
    )

    query = Prospection.query.join(User).filter(User.role == "commercial")
    date_start = request.args.get("date_start")
    date_end = request.args.get("date_end")
    commercial_id = request.args.get("commercial")
    zone = request.args.get("zone")
    specialite = request.args.get("specialite")

    if date_start:
        query = query.filter(Prospection.date >= date_start)
    if date_end:
        query = query.filter(Prospection.date <= date_end)
    if commercial_id:
        query = query.filter(Prospection.commercial_id == commercial_id)
    if zone:
        query = query.filter(User.zone == zone)
    if specialite:
        query = query.filter(Prospection.specialite == specialite)

    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Prospection.date.desc()).paginate(page=page, per_page=25, error_out=False)

    return render_template(
        "admin_dashboard.html",
        commerciaux=commerciaux,
        prospections=pagination.items,
        pagination=pagination,
        top_5_commerciaux=top_5_commerciaux,
        monthly_revenue_labels=monthly_revenue_labels,
        monthly_revenue_data=monthly_revenue_data,
    )


@admin_bp.route("/commercial_dashboard/<username>", methods=["GET", "POST"])
@login_required
@roles_required("admin", "commercial")
def commercial_detail(username):
    if current_user.role == "commercial" and current_user.username != username:
        flash("Accès non autorisé.", "error")
        return render_template("403.html"), 403

    commercial = User.query.filter_by(username=username).first()
    if not commercial:
        flash("Commercial non trouvé.", "error")
        return render_template("404.html"), 404

    page = request.args.get("page", 1, type=int)
    pagination = commercial.prospections.order_by(Prospection.date.desc()).paginate(
        page=page, per_page=25, error_out=False
    )

    form = DownloadExcelForm()

    if request.method == "POST" and "download_excel" in request.form:
        try:
            data = [
                {
                    "Date": p.date.strftime("%Y-%m-%d"),
                    "Nom Client": p.nom_client,
                    "Spécialité": p.specialite,
                    "Structure": p.structure,
                    "Téléphone": p.telephone,
                    "Profils Prospect": p.profils_prospect,
                    "Produits Présentés": p.produits_presentes,
                    "Produits Prescrits": p.produits_prescrits,
                }
                for p in commercial.prospections.order_by(Prospection.date.desc()).all()
            ]
            df = pd.DataFrame(data)
            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="Prospections")
            output.seek(0)
            return send_file(
                output,
                download_name=f"prospections_{username}.xlsx",
                as_attachment=True,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception:
            logger.exception("Erreur export Excel pour %s", username)
            flash("Erreur lors de la génération du fichier Excel.", "error")

    return render_template(
        "commercial_dashboard.html",
        commercial=commercial,
        prospections=pagination.items,
        pagination=pagination,
        form=form,
    )


@admin_bp.route("/export_pdf/<username>")
@login_required
@roles_required("admin", "commercial")
def export_pdf(username):
    if current_user.role == "commercial" and current_user.username != username:
        flash("Accès non autorisé.", "error")
        return render_template("403.html"), 403

    commercial = User.query.filter_by(username=username).first_or_404()
    prospections = commercial.prospections.order_by(Prospection.date.desc()).all()

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(72, 750, f"Prospections de {username}")
    p.setFont("Helvetica", 10)
    y = 720
    for prospection in prospections:
        if y < 60:
            p.showPage()
            p.setFont("Helvetica", 10)
            y = 750
        p.drawString(72, y, f"{prospection.date} - {prospection.nom_client} ({prospection.structure})")
        y -= 18
    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, download_name=f"prospections_{username}.pdf", as_attachment=True, mimetype="application/pdf")
