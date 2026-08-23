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


def _filtered_prospections_query():
    """Requête de référence des visites du dashboard admin.

    Règle métier : 1 Prospection = 1 visite réelle.
    Tous les KPI/tableaux de visites utilisent cette même requête filtrée.
    """
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
    return query


def _aggregate_sales():
    """Agrège les ventes côté PostgreSQL au lieu de charger toutes les lignes en Python."""
    revenue_by_month = {}
    revenue_by_division = {"nasderm": 0.0, "nasmedic": 0.0}
    revenue_by_commercial = {}
    current_month_by_division = {"nasderm": 0.0, "nasmedic": 0.0}
    total_revenue = 0.0
    total_sales_count = 0
    current_month_revenue = 0.0
    current_month_key = date.today().strftime("%Y-%m")

    for sale_model in SALE_MODELS:
        month_expr = func.to_char(sale_model.date, "YYYY-MM")
        amount_expr = func.coalesce(sale_model.quantity, 0) * func.coalesce(sale_model.price, 0)
        rows = (
            db.session.query(
                month_expr.label("month"),
                sale_model.project,
                sale_model.commercial_id,
                func.sum(amount_expr).label("revenue"),
                func.count(sale_model.id).label("sales_count"),
            )
            .group_by(month_expr, sale_model.project, sale_model.commercial_id)
            .all()
        )
        for month, project, commercial_id, revenue, sales_count in rows:
            amount = float(revenue or 0)
            count = int(sales_count or 0)
            revenue_by_month[month] = revenue_by_month.get(month, 0.0) + amount
            revenue_by_division[project] = revenue_by_division.get(project, 0.0) + amount
            if commercial_id is not None:
                revenue_by_commercial[commercial_id] = revenue_by_commercial.get(commercial_id, 0.0) + amount
            total_revenue += amount
            total_sales_count += count
            if month == current_month_key:
                current_month_revenue += amount
                current_month_by_division[project] = current_month_by_division.get(project, 0.0) + amount

    return revenue_by_month, revenue_by_division, revenue_by_commercial, current_month_by_division, total_revenue, total_sales_count, current_month_revenue


def _annual_revenue_for_division(division, year):
    total = 0.0
    for sale_model in SALE_MODELS:
        amount_expr = func.coalesce(sale_model.quantity, 0) * func.coalesce(sale_model.price, 0)
        value = (
            db.session.query(func.coalesce(func.sum(amount_expr), 0))
            .filter(sale_model.project == division, func.extract("year", sale_model.date) == year)
            .scalar()
        )
        total += float(value or 0)
    return total


@admin_bp.route("/admin_dashboard", methods=["GET"])
@login_required
@roles_required("admin")
def dashboard():
    today = date.today()
    revenue_by_month, revenue_by_division, revenue_by_commercial, current_month_by_division, total_revenue, total_sales_count, current_month_revenue = _aggregate_sales()
    monthly_revenue_labels = sorted(revenue_by_month.keys())
    monthly_revenue_data = [revenue_by_month[m] for m in monthly_revenue_labels]

    division_kpis = {}
    for division in ("nasmedic", "nasderm"):
        monthly_target, annual_target = _division_targets(division, today)
        month_actual = current_month_by_division.get(division, 0.0)
        annual_actual = _annual_revenue_for_division(division, today.year)
        month_target = float(monthly_target) if monthly_target is not None else None
        year_target = float(annual_target) if annual_target is not None else None
        division_kpis[division] = {
            "month_actual": month_actual,
            "month_target": month_target,
            "month_pct": (month_actual / month_target * 100) if month_target else None,
            "annual_actual": annual_actual,
            "annual_target": year_target,
            "annual_pct": (annual_actual / year_target * 100) if year_target else None,
        }

    commerciaux = User.query.filter_by(role="commercial").order_by(User.username).all()
    active_commercials_count = User.query.filter_by(role="commercial", is_active_account=True).count()
    commercial_names = {u.id: u.username for u in commerciaux}
    commercial_zones = {u.id: u.zone for u in commerciaux}

    filtered_query = _filtered_prospections_query()
    filtered_visit_counts = dict(
        filtered_query.with_entities(Prospection.commercial_id, func.count(Prospection.id))
        .group_by(Prospection.commercial_id).all()
    )
    total_filtered_visits = sum(filtered_visit_counts.values())

    performance = []
    for commercial_id in set(list(revenue_by_commercial.keys()) + list(filtered_visit_counts.keys())):
        name = commercial_names.get(commercial_id)
        if name:
            performance.append({"username": name, "revenue": revenue_by_commercial.get(commercial_id, 0), "visits": filtered_visit_counts.get(commercial_id, 0)})
    top_revenue = sorted(performance, key=lambda p: p["revenue"], reverse=True)[:10]
    top_prospections = [{"username": commercial_names[cid], "prospections": count} for cid, count in sorted(filtered_visit_counts.items(), key=lambda x: x[1], reverse=True)[:10] if cid in commercial_names]
    top_5_commerciaux = [{"username": commercial_names[cid], "zone": commercial_zones.get(cid), "nombre_visites": count} for cid, count in sorted(filtered_visit_counts.items(), key=lambda x: x[1], reverse=True)[:5] if cid in commercial_names]

    page = request.args.get("page", 1, type=int)
    pagination = filtered_query.order_by(Prospection.date.desc()).paginate(page=page, per_page=25, error_out=False)
    kpis = {
        "total_revenue": total_revenue,
        "current_month_revenue": current_month_revenue,
        "total_visits": total_filtered_visits,
        "active_commercials": active_commercials_count,
        "monthly_avg": (total_revenue / len(monthly_revenue_labels)) if monthly_revenue_labels else 0,
        "months_with_sales": len(monthly_revenue_labels),
        "total_sales_count": total_sales_count,
    }
    active_suppliers = {slug: s for slug, s in SUPPLIERS.items() if not s.get("archived")}
    return render_template("admin_dashboard.html", commerciaux=commerciaux, prospections=pagination.items, pagination=pagination,
                           top_5_commerciaux=top_5_commerciaux, monthly_revenue_labels=monthly_revenue_labels, monthly_revenue_data=monthly_revenue_data,
                           kpis=kpis, revenue_by_division=revenue_by_division, division_kpis=division_kpis, top_revenue=top_revenue,
                           top_prospections=top_prospections, active_suppliers=active_suppliers)


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
            data = [{"Date": p.date.strftime("%Y-%m-%d"), "Nom Client": p.nom_client, "Spécialité": p.specialite, "Structure": p.structure, "Téléphone": p.telephone, "Profils Prospect": p.profils_prospect, "Produits Présentés": p.produits_presentes, "Produits Prescrits": p.produits_prescrits} for p in commercial.prospections.order_by(Prospection.date.desc()).all()]
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
