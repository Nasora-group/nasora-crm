from io import BytesIO

import pandas as pd
from flask import Blueprint, send_file
from flask_login import login_required

from app.models import User
from app.models_clients import Client
from app.utils import roles_required

clients_export_bp = Blueprint("clients_export", __name__)


@clients_export_bp.route("/admin/clients/export-excel")
@login_required
@roles_required("admin")
def export_clients_excel():
    """Exporte l'intégralité de la base NASORA dans un fichier Excel."""
    clients = Client.query.order_by(Client.name.asc()).all()

    rows = []
    for client in clients:
        rows.append({
            "ID": client.id,
            "Professionnel": client.name,
            "Spécialité": client.specialty or "",
            "Structure": client.structure,
            "Établissement": client.establishment or "",
            "Téléphone": client.phone or "",
            "Email": client.email or "",
            "Zone": client.zone or "",
            "Adresse": client.address or "",
            "Potentiel": client.potential,
            "Notes": client.notes or "",
            "Commercial": client.owner.username if client.owner else "",
            "Dernière visite": client.last_visit.strftime("%d/%m/%Y") if client.last_visit else "",
            "Prochaine visite": client.next_visit.strftime("%d/%m/%Y") if client.next_visit else "",
            "Créé le": client.created_at.strftime("%d/%m/%Y %H:%M") if client.created_at else "",
            "Mis à jour le": client.updated_at.strftime("%d/%m/%Y %H:%M") if client.updated_at else "",
        })

    df = pd.DataFrame(rows)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Base NASORA")
        workbook = writer.book
        worksheet = writer.sheets["Base NASORA"]
        header_format = workbook.add_format({"bold": True, "bg_color": "#0f766e", "font_color": "#ffffff", "border": 1})
        for col_num, value in enumerate(df.columns):
            worksheet.write(0, col_num, value, header_format)
        for col_num, column in enumerate(df.columns):
            width = max(12, min(35, max([len(str(column))] + [len(str(v)) for v in df[column].head(500)])))
            worksheet.set_column(col_num, col_num, width)
        worksheet.freeze_panes(1, 0)
        worksheet.autofilter(0, 0, len(df), max(len(df.columns) - 1, 0))

    output.seek(0)
    return send_file(
        output,
        download_name="base_nasora_complete.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
