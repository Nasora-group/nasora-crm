from datetime import date
from io import BytesIO

import pandas as pd
from flask import Blueprint, render_template, request, send_file
from flask_login import login_required

from app.models import User, Prospection
from app.utils import roles_required

prospections_export_bp = Blueprint("prospections_export", __name__)


def _query_from_filters():
    query = Prospection.query.join(User).filter(User.role == "commercial")
    date_start = (request.args.get("date_start") or "").strip()
    date_end = (request.args.get("date_end") or "").strip()
    commercial = (request.args.get("commercial") or "").strip()
    zone = (request.args.get("zone") or "").strip()
    specialite = (request.args.get("specialite") or "").strip()

    if date_start:
        query = query.filter(Prospection.date >= date.fromisoformat(date_start))
    if date_end:
        query = query.filter(Prospection.date <= date.fromisoformat(date_end))
    if commercial:
        query = query.filter(Prospection.commercial_id == int(commercial))
    if zone:
        query = query.filter(User.zone == zone)
    if specialite:
        query = query.filter(Prospection.specialite == specialite)
    return query, date_start, date_end, commercial, zone, specialite


@prospections_export_bp.route("/admin/prospections/export", methods=["GET"])
@login_required
@roles_required("admin")
def export_prospections():
    """Affiche les prospections filtrées et permet leur export Excel complet."""
    query, date_start, date_end, commercial, zone, specialite = _query_from_filters()
    commerciaux = User.query.filter_by(role="commercial").order_by(User.username).all()
    zones = [z for (z,) in User.query.filter(User.role == "commercial", User.zone.isnot(None)).with_entities(User.zone).distinct().order_by(User.zone).all()]
    specialites = [s for (s,) in Prospection.query.with_entities(Prospection.specialite).distinct().order_by(Prospection.specialite).all() if s]

    if request.args.get("download") == "1":
        prospections = query.order_by(Prospection.date.desc(), User.username.asc(), Prospection.id.desc()).all()
        rows = [{
            "Commercial": p.commercial.username,
            "Division": (p.commercial.project or "").upper(),
            "Zone": p.commercial.zone or "",
            "Date": p.date.strftime("%Y-%m-%d"),
            "Nom Client": p.nom_client,
            "Spécialité": p.specialite,
            "Structure": p.structure,
            "Téléphone": p.telephone,
            "Profils Prospect": p.profils_prospect or "",
            "Produits Présentés": p.produits_presentes or "",
            "Produits Prescrits": p.produits_prescrits or "",
        } for p in prospections]
        columns = ["Commercial", "Division", "Zone", "Date", "Nom Client", "Spécialité", "Structure", "Téléphone", "Profils Prospect", "Produits Présentés", "Produits Prescrits"]
        df = pd.DataFrame(rows, columns=columns)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Prospections")
            worksheet = writer.sheets["Prospections"]
            worksheet.freeze_panes(1, 0)
            worksheet.autofilter(0, 0, max(len(df), 1), len(columns) - 1)
            for i, column in enumerate(columns):
                values = [len(str(column))] + [len(str(v)) for v in df[column].fillna("").head(500)]
                worksheet.set_column(i, i, min(max(max(values) + 2, 12), 45))
        output.seek(0)
        suffix = date_start if date_start and date_start == date_end else (f"{date_start}_au_{date_end}" if date_start and date_end else (date_start or date_end or "toutes_dates"))
        return send_file(output, download_name=f"prospections_commerciaux_{suffix}.xlsx", as_attachment=True, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    results_count = query.count()
    return render_template(
        "prospections_export.html",
        prospections=query.order_by(Prospection.date.desc()).limit(100).all(),
        results_count=results_count,
        commerciaux=commerciaux,
        zones=zones,
        specialites=specialites,
        date_start=date_start,
        date_end=date_end,
        commercial=commercial,
        zone=zone,
        specialite=specialite,
    )
