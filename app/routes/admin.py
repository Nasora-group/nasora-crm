import logging
from io import BytesIO
from datetime import date

import pandas as pd
from flask import Blueprint, render_template, request, send_file, flash
from flask_login import login_required, current_user
from sqlalchemy import func
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.extensions import db
from app.forms import DownloadExcelForm, CSRFOnlyForm
from app.models import User, Prospection, SUPPLIERS, SalesObjective
from app.utils import roles_required
from app.visit_metrics import unique_visit_count, unique_visits_by_commercial

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__)

SALE_MODELS = [s["sale_model"] for s in SUPPLIERS.values() if not s.get("archived")]


def _division_targets(division, today):
    try:
        monthly = SalesObjective.query.filter_by(division=division, year=today.year, month=today.month).first()
        annual = SalesObjective.query.filter_by(division=division, year=today.year, month=None).first()
        return (monthly.target_amount if monthly else None, annual.target_amount if annual else None)
    except Exception:
        db.session.rollback()
        logger.warning("Impossible de lire les objectifs pour %s", division, exc_info=True)
        return None, None


@admin_bp.route("/admin_dashboard", methods=["GET"])
@login_required
@roles_required("admin")
def dashboard():
    today = date.today()
    current_month_key = today.strftime("%Y-%m")
    revenue_by_month = {}
    revenue_by_division = {"nasderm": 0.0, "nasmedic": 0.0}
    revenue_by_commercial = {}
    current_month_by_division = {"nasderm": 0.0, "nasmedic": 0.0}
    total_revenue = 0.0
    total_sales_count = 0
    current_month_revenue = 0.0

    for sale_model in SALE_MODELS:
        rows = db.session.query(sale_model.date, sale_model.quantity, sale_model.price, sale_model.project, sale_model.commercial_id).all()
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
                current_month_by_division[project] = current_month_by_division.get(project, 0) + amount

    monthly_revenue_labels = sorted(revenue_by_month.keys())
    monthly_revenue_data = [revenue_by_month[m] for m in monthly_revenue_labels]

    division_kpis = {}
    for division in ("nasmedic", "nasderm"):
        monthly_target, annual_target = _division_targets(division, today)
        month_actual = current_month_by_division.get(division, 0.0)
        annual_actual = 0.0
        for sale_model in SALE_MODELS:
            rows = db.session.query(sale_model.date, sale_model.quantity, sale_model.price).filter(sale_model.project == division).all()
            annual_actual += sum((q or 0) * (p or 0) for d, q, p in rows if d.year == today.year)
        division_kpis[division] = {
            "month_actual": month_actual,
            "month_target": monthly_target,
            "month_pct": (month_actual / monthly_target * 100) if monthly_target else None,
            "annual_actual": annual_actual,
            "annual_target": annual_target,
            "annual_pct": (annual_actual / annual_target * 100) if annual_target else None,
        }

    commerciaux = User.query.filter_by(role="commercial").order_by(User.username).all()
    active_commercials_count = User.query.filter_by(role="commercial", is_active_account=True).count()

    # Visites réelles = Prospections. ClientVisit est désormais le miroir CRM.
    total_visits = unique_visit_count()
    visits_by_commercial = unique_visits_by_commercial()
    commercial_names = {u.id: u.username for u in commerciaux}
    commercial_zones = {u.id: u.zone for u in commerciaux}

    performance = []
    for commercial_id in set(list(revenue_by_commercial.keys()) + list(visits_by_commercial.keys())):
        name = commercial_names.get(commercial_id)
        if not name:
            continue
        performance.append({"username": name, "revenue": revenue_by_commercial.get(commercial_id, 0), "visits": visits_by_commercial.get(commercial_id, 0)})

    top_revenue = sorted(performance, key=lambda p: p["revenue"], reverse=True)[:10]

    # Source unique du graphique et du tableau de prospections.
    # Les mêmes filtres sont appliqués aux deux pour garantir leur cohérence.
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

    prospections_by_commercial = dict(
        query.with_entities(
            Prospection.commercial_id,
            func.count(Prospection.id),
        )
        .group_by(Prospection.commercial_id)
        .all()
    )
    top_prospections = [
        {"username": commercial_names[cid], "prospections": count}
        for cid, count in sorted(prospections_by_commercial.items(), key=lambda item: item[1], reverse=True)[:10]
        if cid in commercial_names
    ]

    # Le classement des visites utilise exactement la même source Prospection
    # et les mêmes filtres que le graphique.
    top_5_commerciaux = [
        {"username": commercial_names[cid], "zone": commercial_zones.get(cid), "nombre_visites": count}
        for cid, count in sorted(prospections_by_commercial.items(), key=lambda item: item[1], reverse=True)[:5]
        if cid in commercial_names
    ]

    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Prospection.date.desc()).paginate(page=page, per_page=25, error_out=False)

    kpis = {
        "total_revenue": total_revenue,
        "current_month_revenue": current_month_revenue,
        "total_visits": total_visits,
        "active_commercials": active_commercials_count,
        "monthly_avg": (total_revenue / len(monthly_revenue_labels)) if monthly_revenue_labels else 0,
        "months_with_sales": len(monthly_revenue_labels),
        "total_sales_count": total_sales_count,
    }

    active_suppliers = {slug: s for slug, s in SUPPLIERS.items() if not s.get("archived")}
    return render_template("admin_dashboard.html", commerciaux=commerciaux, prospections=pagination.items, pagination=pagination,
                           top_5_commerciaux=top_5_commerciaux, monthly_revenue_labels=monthly_revenue_labels,
                           monthly_revenue_data=monthly_revenue_data, kpis=kpis, revenue_by_division=revenue_by_division,
                           division_kpis=division_kpis, top_revenue=top_revenue, top_prospections=top_prospections,
                           active_suppliers=active_suppliers)


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
    pagination = commercial.prospections.order_by(Prospection.date.desc()).paginate(page=page, per_page=25, error_out=False)
    form = DownloadExcelForm()
    if request.method == "POST" and "download_excel" in request.form:
        try:
            data = [{"Date": p.date.strftime("%Y-%m-%d"), "Nom Client": p.nom_client, "Spécialité": p.specialite,
                     "Structure": p.structure, "Téléphone": p.telephone, "Profils Prospect": p.profils_prospect,
                     "Produits Présentés": p.produits_presentes, "Produits Prescrits": p.produits_prescrits}
                    for p in commercial.prospections.order_by(Prospection.date.desc()).all()]
            df = pd.DataFrame(data)
            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="Prospections")
            output.seek(0)
            return send_file(output, download_name=f"prospections_{username}.xlsx", as_attachment=True, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception:
            logger.exception("Erreur export Excel pour %s", username)
            flash("Erreur lors de la génération du fichier Excel.", "error")
    return render_template("commercial_dashboard.html", commercial=commercial, prospections=pagination.items, pagination=pagination, form=form, delete_form=CSRFOnlyForm())


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
            p.showPage(); p.setFont("Helvetica", 10); y = 750
        p.drawString(72, y, f"{prospection.date} - {prospection.nom_client} ({prospection.structure})")
        y -= 18
    p.showPage(); p.save(); buffer.seek(0)
    return send_file(buffer, download_name=f"prospections_{username}.pdf", as_attachment=True, mimetype="application/pdf")
