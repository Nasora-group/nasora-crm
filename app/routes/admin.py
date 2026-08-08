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
    from datetime import date

    today = date.today()
    current_month_key = today.strftime("%Y-%m")

    revenue_by_month = {}
    revenue_by_division = {"nasderm": 0.0, "nasmedic": 0.0}
    revenue_by_commercial = {}
    total_revenue = 0.0
    total_sales_count = 0
    current_month_revenue = 0.0

    for sale_model in SALE_MODELS:
        rows = db.session.query(
            sale_model.date, sale_model.quantity, sale_model.price,
            sale_model.project, sale_model.commercial_id,
        ).all()
        for sale_date, quantity, price, project, commercial_id in rows:
            amount = (quantity or 0) * (price or 0)
            month = sale_date.strftime("%Y-%m")
            revenue_by_month.setdefault(month, 0)
            revenue_by_month[month] += amount
            revenue_by_division[project] = revenue_by_division.get(project, 0) + amount
            revenue_by_commercial.setdefault(commercial_id, 0)
            revenue_by_commercial[commercial_id] += amount
            total_revenue += amount
            total_sales_count += 1
            if month == current_month_key:
                current_month_revenue += amount

    monthly_revenue_labels = sorted(revenue_by_month.keys())
    monthly_revenue_data = [revenue_by_month[m] for m in monthly_revenue_labels]

    commerciaux = User.query.filter_by(role="commercial").order_by(User.username).all()
    active_commercials_count = User.query.filter_by(role="commercial", is_active_account=True).count()
    total_visits = Prospection.query.count()

    visits_by_commercial_rows = (
        db.session.query(User.id, User.username, func.count(Prospection.id).label("nombre_visites"))
        .join(Prospection, Prospection.commercial_id == User.id)
        .group_by(User.id)
        .all()
    )
    visits_by_commercial = {row.id: row.nombre_visites for row in visits_by_commercial_rows}

    commercial_names = {u.id: u.username for u in commerciaux}

    performance = []
    for commercial_id in set(list(revenue_by_commercial.keys()) + list(visits_by_commercial.keys())):
        name = commercial_names.get(commercial_id)
        if not name:
            continue
        performance.append({
            "username": name,
            "revenue": revenue_by_commercial.get(commercial_id, 0),
            "visits": visits_by_commercial.get(commercial_id, 0),
        })

    top_revenue = sorted(performance, key=lambda p: p["revenue"], reverse=True)[:10]
    top_visits = sorted(performance, key=lambda p: p["visits"], reverse=True)[:10]

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
    commercial_id_filter = request.args.get("commercial")
    zone = request.args.get("zone")
    specialite = request.args.get("specialite")

    if date_start:
        query = query.filter(Prospection.date >= date_start)
    if date_end:
        query = query.filter(Prospection.date <= date_end)
    if commercial_id_filter:
        query = query.filter(Prospection.commercial_id == commercial_id_filter)
    if zone:
        query = query.filter(User.zone == zone)
    if specialite:
        query = query.filter(Prospection.specialite == specialite)

    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Prospection.date.desc()).paginate(page=page, per_page=25, error_out=False)

    kpis = {
        "total_revenue": total_revenue,
        "current_month_revenue": current_month_revenue,
        "total_visits": total_visits,
        "active_commercials": active_commercials_count,
        "avg_sale": (total_revenue / total_sales_count) if total_sales_count else 0,
        "total_sales_count": total_sales_count,
    }

    return render_template(
        "admin_dashboard.html",
        commerciaux=commerciaux,
        prospections=pagination.items,
        pagination=pagination,
        top_5_commerciaux=top_5_commerciaux,
        monthly_revenue_labels=monthly_revenue_labels,
        monthly_revenue_data=monthly_revenue_data,
        kpis=kpis,
        revenue_by_division=revenue_by_division,
        top_revenue=top_revenue,
        top_visits=top_visits,
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
