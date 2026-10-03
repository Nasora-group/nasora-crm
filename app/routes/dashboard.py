import csv
import logging
import re
import unicodedata
from io import BytesIO, StringIO
from collections import Counter
from datetime import date, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request, Response, send_file
from flask_login import login_required, current_user
from sqlalchemy import bindparam, func, text
import pandas as pd

from app.extensions import db
from app.forms import ProspectionForm, CSRFOnlyForm
from app.models import Prospection, Planning, User, get_active_products_for_division, STRUCTURES
from app.models_clients import Client, ClientVisit
from app.utils import roles_required
from app.routes.revenue import _monthly_revenue_for_division, _objectives_kpis
from app.visit_metrics import professional_key
from app.utils import decode_planning_slot
from app.services.admin_notifications import notify_admins
from app.services.audit import audit_event

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__)


def _parse_products(raw):
    return [p.strip() for p in (raw or "").split(",") if p.strip()]


def _set_product_choices(form, division, existing_values=None):
    active = get_active_products_for_division(division)
    choices = [(name, name) for name in active]
    for value in (existing_values or []):
        if value and value not in active:
            choices.append((value, f"{value} (non disponible)"))
    form.produits_presentes.choices = choices
    form.produits_prescrits.choices = choices


def _set_structure_choices(form):
    form.structure.choices = [(value, label) for value, label in STRUCTURES]


def _normalize_text(value):
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower()).strip())


def _normalize_phone(value):
    return re.sub(r"\D", "", value or "")


def _invalid_phone(value):
    raw = (value or "").strip().lower()
    return raw in {"", "na", "n/a", "nc", "non renseigne", "non renseigné", "0"} or len(_normalize_phone(raw)) < 6


def _find_client_for_prospection(prospection):
    phone = (prospection.telephone or "").strip()
    name = (prospection.nom_client or "").strip()
    normalized_phone = _normalize_phone(phone)
    normalized_name = _normalize_text(name)
    owner_scope = (Client.owner_id.is_(None) | (Client.owner_id == prospection.commercial_id))
    if normalized_phone and not _invalid_phone(phone):
        candidates = Client.query.filter(
            Client.phone.isnot(None),
            owner_scope,
        ).all()
        for client in candidates:
            if _normalize_phone(client.phone) == normalized_phone:
                return client
    if not normalized_name:
        return None
    candidates = Client.query.filter(
        Client.name.isnot(None),
        owner_scope,
        func.lower(Client.name) == name.lower(),
    ).all()
    owned = [c for c in candidates if _normalize_text(c.name) == normalized_name]
    if owned:
        return sorted(owned, key=lambda c: (c.owner_id is not None, c.id))[0]
    return None


def _sync_client_fields(prospection, client, establishment=None):
    phone = (prospection.telephone or "").strip()
    valid_phone = not _invalid_phone(phone)
    establishment = (establishment or "").strip() or None
    if client is None:
        client = Client(
            name=prospection.nom_client.strip(),
            specialty=prospection.specialite.strip() or None,
            structure=prospection.structure.strip(),
            establishment=establishment,
            zone=(prospection.zone or "").strip() or None,
            region=(prospection.region or "").strip() or None,
            address=(prospection.address or "").strip() or None,
            phone=phone if valid_phone else None,
            potential=3,
            owner_id=prospection.commercial_id,
            last_visit=prospection.date,
        )
        db.session.add(client)
        db.session.flush()
    else:
        client.name = prospection.nom_client.strip() or client.name
        client.specialty = prospection.specialite.strip() or client.specialty
        client.structure = prospection.structure.strip() or client.structure
        if establishment:
            client.establishment = establishment
        if prospection.zone:
            client.zone = prospection.zone.strip()
        if prospection.region:
            client.region = prospection.region.strip()
        if prospection.address:
            client.address = prospection.address.strip()
        if valid_phone:
            client.phone = phone
        if client.owner_id is None:
            client.owner_id = prospection.commercial_id
    return client


def _sync_professional_from_prospection(prospection, establishment=None, existing_client=None, previous_payload=None):
    client = existing_client or _find_client_for_prospection(prospection)
    client = _sync_client_fields(prospection, client, establishment=establishment)
    pp = prospection.produits_presentes or None
    pr = prospection.produits_prescrits or None
    report = prospection.profils_prospect or None
    visit = ClientVisit.query.filter_by(prospection_id=prospection.id, is_duplicate=False).first()
    if visit is None and previous_payload and previous_payload.get("client_id"):
        visit = ClientVisit.query.filter_by(
            client_id=previous_payload["client_id"],
            commercial_id=prospection.commercial_id,
            date=previous_payload["date"],
            products_presented=previous_payload["products_presented"],
            products_prescribed=previous_payload["products_prescribed"],
            report=previous_payload["report"],
            is_duplicate=False,
        ).first()
        if visit is not None and visit.prospection_id is None:
            visit.prospection_id = prospection.id
    if visit is None:
        visit = ClientVisit(
            client_id=client.id,
            commercial_id=prospection.commercial_id,
            prospection_id=prospection.id,
            date=prospection.date,
            products_presented=pp,
            products_prescribed=pr,
            report=report,
        )
        db.session.add(visit)
    else:
        visit.client_id = client.id
        visit.commercial_id = prospection.commercial_id
        visit.prospection_id = prospection.id
        visit.date = prospection.date
        visit.products_presented = pp
        visit.products_prescribed = pr
        visit.report = report
    prospection.client_id = client.id
    client.last_visit = prospection.date


def _sync_professional_from_existing_prospection(prospection, establishment=None, existing_client=None, previous_payload=None):
    return _sync_professional_from_prospection(prospection, establishment=establishment, existing_client=existing_client, previous_payload=previous_payload)


def _delete_linked_records_for_prospection(prospection):
    visit = ClientVisit.query.filter_by(prospection_id=prospection.id, is_duplicate=False).first()
    if visit is not None:
        visit.prospection_id = None
        db.session.delete(visit)
        return
    client = _find_client_for_prospection(prospection)
    if client is None:
        return
    pp = prospection.produits_presentes or None
    pr = prospection.produits_prescrits or None
    report = prospection.profils_prospect or None
    visit = ClientVisit.query.filter_by(
        client_id=client.id,
        commercial_id=prospection.commercial_id,
        date=prospection.date,
        products_presented=pp,
        products_prescribed=pr,
        report=report,
        is_duplicate=False,
        prospection_id=None,
    ).first()
    if visit is not None:
        db.session.delete(visit)


def _planning_context_for_date(visit_date):
    """Retourne le programme correspondant strictement à la date sélectionnée."""
    if not visit_date:
        return {"planning": None, "day": None, "day_label": None, "entries": []}

    # La date saisie est la seule référence pour déterminer le programme.
    # La date du jour n'intervient que lorsque aucune date n'a été saisie.
    # Un planning est enregistré avec le lundi comme date de référence.
    # Pour une date sélectionnée, on retrouve donc exactement le planning
    # de la semaine concernée, sans jamais utiliser la date du jour.
    monday = visit_date - timedelta(days=visit_date.weekday())
    planning = (
        Planning.query
        .filter(
            Planning.commercial_id == current_user.id,
            Planning.date == monday,
        )
        .order_by(Planning.id.desc())
        .first()
    )
    if planning is None:
        return {"planning": None, "day": None, "day_label": None, "entries": []}

    days = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
    labels = {
        "lundi": "Lundi",
        "mardi": "Mardi",
        "mercredi": "Mercredi",
        "jeudi": "Jeudi",
        "vendredi": "Vendredi",
        "samedi": "Samedi",
        "dimanche": "Dimanche",
    }
    day = days[visit_date.weekday()]
    entries = []
    for structure, name in decode_planning_slot(getattr(planning, day)):
        # Un même champ du planning peut contenir plusieurs établissements
        # séparés par des virgules. Chaque établissement devient une ligne
        # distincte lors de la saisie d'une prospection.
        names = [item.strip() for item in (name or "").split(",") if item.strip()]
        if not names:
            names = [""]
        for establishment_name in names:
            entries.append({"structure": structure, "name": establishment_name})
    return {"planning": planning, "day": day, "day_label": labels[day], "entries": entries}

def _validate_location(zone, region, address=None, required=True):
    zone = (zone or "").strip()
    region = (region or "").strip()
    address = (address or "").strip()
    if required and (not zone or not region or not address):
        return "La région, la zone et l'adresse précise sont obligatoires."
    if not zone or not region:
        return None
    if region == "DAKAR" and zone == "HORS DAKAR":
        return "Pour la région de Dakar, sélectionne une zone de Dakar."
    if region != "DAKAR" and zone != "HORS DAKAR":
        return "Pour une autre région du Sénégal, la zone doit être HORS DAKAR."
    return None

def _dashboard_activity_for_date(visit_date, planning_context):
    """Calcule les indicateurs V3.1 sans modifier les données existantes."""
    rows = Prospection.query.filter_by(
        commercial_id=current_user.id,
        date=visit_date,
    ).all()

    planned_keys = {
        (_normalize_text(entry["structure"]), _normalize_text(entry["name"]))
        for entry in planning_context.get("entries", [])
        if entry.get("name")
    }
    realized_keys = set()
    hors_planning = 0
    professional_ids = set()
    professional_names = set()

    for row in rows:
        if row.planning_id is None:
            hors_planning += 1
        else:
            key = (
                _normalize_text(row.structure),
                _normalize_text(row.establishment or ""),
            )
            if key in planned_keys:
                realized_keys.add(key)

        if row.client_id:
            professional_ids.add(row.client_id)
        else:
            fallback = _normalize_text(row.nom_client)
            if fallback:
                professional_names.add(fallback)

    planned_total = len(planned_keys)
    realized_total = len(realized_keys)
    tracking_active = visit_date >= date(2026, 10, 3)
    realization_rate = round((realized_total / planned_total) * 100, 1) if planned_total and tracking_active else None

    status_by_key = {
        key: (
            "Réalisé" if key in realized_keys else "À faire"
        ) if tracking_active else "Non suivi"
        for key in planned_keys
    }
    relance_rows = [row for row in rows if row.a_revoir and (row.date_relance is None or row.date_relance <= visit_date)]
    planning_rows = []
    for entry in planning_context.get("entries", []):
        key = (_normalize_text(entry["structure"]), _normalize_text(entry["name"]))
        planning_rows.append({
            "structure": entry["structure"],
            "name": entry["name"],
            "status": status_by_key.get(key, "À faire"),
        })

    return {
        "planned_total": planned_total,
        "realized_total": realized_total,
        "hors_planning": hors_planning,
        "professionals_visited": len(professional_ids) + len(professional_names),
        "realization_rate": realization_rate,
        "tracking_active": tracking_active,
        "planning_rows": planning_rows,
        "relances_a_traiter": len(relance_rows),
    }


def _render_dashboard(form, selected_date=None):
    labels, totals, _ = _monthly_revenue_for_division(current_user.project)
    sales_kpis = _objectives_kpis(current_user.project, labels, totals)
    visit_date = selected_date or form.date.data or date.today()
    planning_context = _planning_context_for_date(visit_date)
    dashboard_activity = _dashboard_activity_for_date(visit_date, planning_context)
    return render_template(
        "dashboard.html",
        form=form,
        sales_kpis=sales_kpis,
        planning_context=planning_context,
        dashboard_activity=dashboard_activity,
    )


@dashboard_bp.route("/dashboard", methods=["GET", "POST"])
@login_required
@roles_required("commercial")
def index():
    form = ProspectionForm()
    _set_structure_choices(form)
    _set_product_choices(form, current_user.project)

    # La date sélectionnée dans l'écran est la seule référence du programme.
    # Les dates passées et futures sont acceptées.
    selected_date = None
    if not form.is_submitted():
        requested_date = request.args.get("date", "").strip()
        try:
            selected_date = date.fromisoformat(requested_date) if requested_date else date.today()
        except ValueError:
            selected_date = date.today()
        form.date.data = selected_date

    if form.is_submitted():
        _set_structure_choices(form)
        _set_product_choices(form, current_user.project)
        if not form.validate():
            flash("Veuillez corriger les champs indiqués.", "error")
            return _render_dashboard(form, form.date.data)
        planning_context = _planning_context_for_date(form.date.data)
        location_error = _validate_location(form.zone.data, form.region.data, form.address.data, required=True)
        if location_error:
            flash(location_error, "error")
            return _render_dashboard(form, form.date.data)
        is_hors_planning = bool(form.hors_planning.data)
        if planning_context["planning"] is not None and not is_hors_planning:
            exact_match = any(
                _normalize_text(entry["structure"]) == _normalize_text(form.structure.data)
                and _normalize_text(entry["name"]) == _normalize_text(form.nom_structure.data)
                for entry in planning_context["entries"]
            )
            if not exact_match:
                flash("Cette structure n'est pas prévue dans le planning de cette journée. Sélectionne une structure planifiée ou active « Prospection hors planning ».", "error")
                return _render_dashboard(form, form.date.data)
        try:
            prospection = Prospection(
                commercial_id=current_user.id,
                date=form.date.data,
                nom_client=form.nom_client.data.strip(),
                specialite=form.specialite.data.strip(),
                structure=form.structure.data.strip(),
                telephone=form.telephone.data.strip(),
                zone=form.zone.data.strip(),
                region=form.region.data.strip(),
                address=form.address.data.strip(),
                planning_id=(None if is_hors_planning else (planning_context["planning"].id if planning_context["planning"] else None)),
                planning_day=(None if is_hors_planning else planning_context["day"]),
                profils_prospect=(form.profils_prospect.data or "").strip(),
                produits_presentes=", ".join(form.produits_presentes.data or []),
                produits_prescrits=", ".join(form.produits_prescrits.data or []),
                establishment=form.nom_structure.data.strip(),
                a_revoir=bool(form.a_revoir.data),
                date_relance=form.date_relance.data if form.a_revoir.data else None,
                motif_relance=(form.motif_relance.data or "").strip() or None,
            )
            db.session.add(prospection)
            # La route reste responsable de la transaction complète:
            # Prospection -> Client -> ClientVisit.
            db.session.flush()
            _sync_professional_from_prospection(
                prospection,
                establishment=form.nom_structure.data,
            )
            db.session.flush()
            linked_visits = ClientVisit.query.filter_by(
                prospection_id=prospection.id,
                is_duplicate=False,
            ).order_by(ClientVisit.id.asc()).all()
            for duplicate_visit in linked_visits[1:]:
                duplicate_visit.prospection_id = None
                db.session.delete(duplicate_visit)
            notify_admins(current_user, "prospection_created", "Nouvelle prospection", "Une nouvelle prospection a été enregistrée.", "dashboard.prospections")
            db.session.commit()
            audit_event("prospection_created", "prospection", prospection.id, {"client": prospection.nom_client, "date": prospection.date.isoformat()})
            flash("Prospection enregistrée avec succès.", "success")
            return redirect(url_for("dashboard.index"))
        except Exception:
            db.session.rollback()
            logger.exception("Erreur lors de l'enregistrement d'une prospection")
            flash("Impossible d'enregistrer la prospection. Aucun changement n'a été appliqué.", "error")
            return _render_dashboard(form, form.date.data)
    return _render_dashboard(form, selected_date or form.date.data)


@dashboard_bp.route("/dashboard/prospections", methods=["GET"])
@login_required
@roles_required("commercial")
def prospections():
    page = Prospection.query.filter_by(commercial_id=current_user.id).order_by(
        Prospection.date.desc(), Prospection.id.desc()
    ).paginate(page=request.args.get("page", 1, type=int), per_page=50, error_out=False)
    rows = page.items
    client_ids = {row.client_id for row in rows if row.client_id}
    clients_by_id = {}
    if client_ids:
        clients_by_id = {
            client.id: client
            for client in Client.query.filter(Client.id.in_(client_ids)).all()
        }
    establishments_by_prospection = {}
    for row in rows:
        client = clients_by_id.get(row.client_id)
        establishments_by_prospection[row.id] = (
            (row.establishment or "").strip()
            or (client.establishment if client and client.establishment else "")
        )
    return render_template(
        "dashboard_prospections.html",
        prospections=rows,
        prospections_pagination=page,
        planning_statuses={},
        establishments_by_prospection=establishments_by_prospection,
    )


@dashboard_bp.route("/dashboard/prospection/<int:prospection_id>/modifier", methods=["GET", "POST"])
@login_required
@roles_required("commercial")
def edit_prospection(prospection_id):
    prospection = Prospection.query.get_or_404(prospection_id)
    if prospection.commercial_id != current_user.id:
        return render_template("403.html"), 403
    existing_presentes = _parse_products(prospection.produits_presentes)
    existing_prescrits = _parse_products(prospection.produits_prescrits)
    form = ProspectionForm(obj=prospection)
    _set_structure_choices(form)
    _set_product_choices(form, current_user.project, set(existing_presentes) | set(existing_prescrits))
    if not form.is_submitted():
        form.produits_presentes.data = existing_presentes
        form.produits_prescrits.data = existing_prescrits
        client = _find_client_for_prospection(prospection)
        form.nom_structure.data = (prospection.establishment or (client.establishment if client else "")) or ""
        form.zone.data = prospection.zone or (client.zone if client else "") or "HORS DAKAR"
        form.region.data = prospection.region or (client.region if client else "") or "DAKAR"
        form.address.data = prospection.address or (client.address if client else "") or ""
        form.hors_planning.data = prospection.planning_id is None
    if form.validate_on_submit():
        planning_context = _planning_context_for_date(form.date.data)
        location_error = _validate_location(form.zone.data, form.region.data, form.address.data, required=False)
        if location_error:
            flash(location_error, "error")
            return render_template("edit_prospection.html", form=form, prospection=prospection, planning_context=planning_context)
        is_hors_planning = bool(form.hors_planning.data)
        if planning_context["planning"] is not None and not is_hors_planning:
            exact_match = any(
                _normalize_text(entry["structure"]) == _normalize_text(form.structure.data)
                and _normalize_text(entry["name"]) == _normalize_text(form.nom_structure.data)
                for entry in planning_context["entries"]
            )
            if not exact_match:
                flash("Cette structure n'est pas prévue dans le planning de cette journée.", "error")
                return render_template("edit_prospection.html", form=form, prospection=prospection, planning_context=planning_context)
        try:
            linked_visit = ClientVisit.query.filter_by(prospection_id=prospection.id, is_duplicate=False).first()
            previous_client = linked_visit.client if linked_visit is not None else _find_client_for_prospection(prospection)
            previous_payload = {"client_id": previous_client.id if previous_client else None, "date": prospection.date, "products_presented": prospection.produits_presentes or None, "products_prescribed": prospection.produits_prescrits or None, "report": prospection.profils_prospect or None}
            prospection.date = form.date.data
            prospection.nom_client = form.nom_client.data.strip()
            prospection.specialite = form.specialite.data.strip()
            prospection.structure = form.structure.data.strip()
            prospection.establishment = form.nom_structure.data.strip()
            prospection.telephone = form.telephone.data.strip()
            prospection.zone = form.zone.data.strip()
            prospection.region = form.region.data.strip()
            prospection.address = form.address.data.strip()
            prospection.planning_id = None if is_hors_planning else (planning_context["planning"].id if planning_context["planning"] else None)
            prospection.planning_day = None if is_hors_planning else planning_context["day"]
            prospection.a_revoir = bool(form.a_revoir.data)
            prospection.date_relance = form.date_relance.data if form.a_revoir.data else None
            prospection.motif_relance = (form.motif_relance.data or "").strip() or None
            prospection.profils_prospect = (form.profils_prospect.data or "").strip()
            prospection.produits_presentes = ", ".join(form.produits_presentes.data or [])
            prospection.produits_prescrits = ", ".join(form.produits_prescrits.data or [])
            _sync_professional_from_existing_prospection(prospection, form.nom_structure.data, existing_client=previous_client, previous_payload=previous_payload)
            notify_admins(current_user, "prospection_updated", "Prospection modifiée", "Une prospection a été modifiée.", "dashboard.prospections")
            db.session.commit()
            flash("Prospection mise à jour avec succès.", "success")
            return redirect(url_for("dashboard.prospections"))
        except Exception:
            db.session.rollback()
            logger.exception("Erreur lors de la modification de la prospection #%s", prospection_id)
            flash("Erreur lors de la mise à jour.", "error")
    return render_template("edit_prospection.html", form=form, prospection=prospection, planning_context=_planning_context_for_date(prospection.date))


@dashboard_bp.route("/dashboard/prospection/<int:prospection_id>/supprimer", methods=["POST"])
@login_required
@roles_required("commercial")
def delete_prospection(prospection_id):
    form = CSRFOnlyForm()
    prospection = Prospection.query.get_or_404(prospection_id)
    if prospection.commercial_id != current_user.id:
        return redirect(url_for("dashboard.prospections"))
    if form.validate_on_submit():
        try:
            _delete_linked_records_for_prospection(prospection)
            db.session.delete(prospection)
            db.session.commit()
            flash("Prospection supprimée avec succès.", "success")
        except Exception:
            db.session.rollback()
            logger.exception("Erreur lors de la suppression de la prospection #%s", prospection_id)
            flash("Impossible de supprimer la prospection. Aucun changement n'a été appliqué.", "error")
    return redirect(url_for("dashboard.prospections"))


def _visit_targets_for_commercials(commercials):
    """Read per-commercial visit targets with a safe 100-visit fallback."""
    targets = {commercial.id: 100 for commercial in commercials}
    if not commercials:
        return targets
    try:
        statement = text("SELECT commercial_id, target FROM visit_objective WHERE commercial_id IN :ids").bindparams(bindparam("ids", expanding=True))
        rows = db.session.execute(statement, {"ids": [commercial.id for commercial in commercials]}).mappings().all()
        for row in rows:
            targets[int(row["commercial_id"])] = int(row["target"])
    except Exception:
        db.session.rollback()
        logger.warning("Impossible de lire les objectifs de visites; fallback à 100.", exc_info=True)
    return targets


@dashboard_bp.route("/admin/dashboard-direction/export.csv", methods=["GET"])
@login_required
@roles_required("admin")
def direction_export_csv():
    """Exporte le reporting Direction par visiteur avec les mêmes filtres."""
    rows = _direction_reporting_rows()
    output = StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Visiteur médical", "Prospections", "Professionnels visités", "Structures", "Zones couvertes", "Régions couvertes"])
    for row in rows:
        writer.writerow([row["name"], row["prospections"], row["professionals"], row["structures"], row["zones"], row["regions"]])
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=reporting_direction.csv"})


@dashboard_bp.route("/admin/dashboard-direction/export.xlsx", methods=["GET"])
@login_required
@roles_required("admin")
def direction_export_excel():
    """Exporte le reporting Direction par visiteur en Excel."""
    rows = _direction_reporting_rows()
    df = pd.DataFrame(rows, columns=["name", "prospections", "professionals", "structures", "zones", "regions"])
    df = df.rename(columns={
        "name": "Visiteur médical", "prospections": "Prospections", "professionals": "Professionnels visités",
        "structures": "Structures", "zones": "Zones couvertes", "regions": "Régions couvertes"
    })
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Reporting Direction")
        ws = writer.sheets["Reporting Direction"]
        ws.freeze_panes(1, 0)
        ws.autofilter(0, 0, max(len(df), 1), max(len(df.columns) - 1, 0))
        for i, column in enumerate(df.columns):
            ws.set_column(i, i, min(max(16, len(column) + 2), 32))
    output.seek(0)
    return send_file(output, download_name="reporting_direction.xlsx", as_attachment=True, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _direction_reporting_rows():
    date_start_raw = (request.args.get("date_start") or "").strip()
    date_end_raw = (request.args.get("date_end") or "").strip()
    commercial_raw = (request.args.get("commercial_id") or "").strip()
    zone = (request.args.get("zone") or "").strip()
    region = (request.args.get("region") or "").strip()
    specialite = (request.args.get("specialite") or "").strip()
    def parse(value):
        try:
            return date.fromisoformat(value) if value else None
        except ValueError:
            return None
    start = parse(date_start_raw); end = parse(date_end_raw)
    cid = int(commercial_raw) if commercial_raw.isdigit() else None
    query = Prospection.query.join(User, Prospection.commercial_id == User.id).filter(User.role == "commercial")
    if start: query = query.filter(Prospection.date >= start)
    if end: query = query.filter(Prospection.date <= end)
    if cid: query = query.filter(Prospection.commercial_id == cid)
    if zone: query = query.filter(Prospection.zone == zone)
    if region: query = query.filter(Prospection.region == region)
    if specialite: query = query.filter(Prospection.specialite == specialite)
    rows = query.with_entities(Prospection.date, Prospection.nom_client, Prospection.establishment, Prospection.structure, Prospection.commercial_id, Prospection.zone, Prospection.region, User.username).all()
    commercials = User.query.filter_by(role="commercial").order_by(User.username).all()
    result=[]
    for c in commercials:
        own=[r for r in rows if r.commercial_id==c.id]
        pros={professional_key(r) for r in own if professional_key(r)}
        structures={_normalize_text(r.establishment or r.nom_client or r.structure) for r in own if _normalize_text(r.establishment or r.nom_client or r.structure)}
        zones={(r.zone or "").strip() for r in own if (r.zone or "").strip()}
        regions={(r.region or "").strip() for r in own if (r.region or "").strip()}
        result.append({"name":c.username,"prospections":len(own),"professionals":len(pros),"structures":len(structures),"zones":len(zones),"regions":len(regions)})
    if cid:
        result=[r for r in result if any(c.id==cid and c.username==r["name"] for c in commercials)]
    return result


@dashboard_bp.route("/admin/dashboard-direction", methods=["GET"])
@login_required
@roles_required("admin")
def direction():
    """Dashboard Direction : pilotage de l'activité terrain, sans CA ni ventes."""
    date_start_raw = (request.args.get("date_start") or "").strip()
    date_end_raw = (request.args.get("date_end") or "").strip()
    commercial_raw = (request.args.get("commercial_id") or "").strip()
    zone = (request.args.get("zone") or "").strip()
    specialite = (request.args.get("specialite") or "").strip()
    region = (request.args.get("region") or "").strip()

    def parse_date(value):
        try:
            return date.fromisoformat(value) if value else None
        except ValueError:
            return None

    date_start = parse_date(date_start_raw)
    date_end = parse_date(date_end_raw)
    commercial_id = int(commercial_raw) if commercial_raw.isdigit() else None

    query = Prospection.query.join(User, Prospection.commercial_id == User.id).filter(User.role == "commercial")
    if date_start:
        query = query.filter(Prospection.date >= date_start)
    if date_end:
        query = query.filter(Prospection.date <= date_end)
    if commercial_id:
        query = query.filter(Prospection.commercial_id == commercial_id)
    if zone:
        query = query.filter(Prospection.zone == zone)
    if region:
        query = query.filter(Prospection.region == region)
    if specialite:
        query = query.filter(Prospection.specialite == specialite)

    # Le dashboard n'affiche pas les objets Prospection eux-mêmes.
    # On ne charge donc que les colonnes nécessaires aux KPI, ce qui réduit
    # fortement la mémoire consommée lorsque l'historique devient volumineux.
    metric_rows = query.with_entities(
        Prospection.date,
        Prospection.nom_client,
        Prospection.telephone,
        Prospection.structure,
        Prospection.establishment,
        Prospection.specialite,
        Prospection.commercial_id,
        Prospection.zone,
        Prospection.region,
        User.username,
    ).all()

    total_prospections = len(metric_rows)
    professionals = {
        professional_key(row)
        for row in metric_rows
        if professional_key(row)
    }
    structures = {
        (_normalize_text(row.establishment or row.nom_client), row.commercial_id)
        for row in metric_rows
        if _normalize_text(row.establishment or row.nom_client)
    }
    specialites_counter = Counter(
        (row.specialite or "Non renseignée").strip() or "Non renseignée"
        for row in metric_rows
    )
    zones_counter = Counter((row.zone or "Non renseignée").strip() or "Non renseignée" for row in metric_rows)
    regions_counter = Counter((row.region or "Non renseignée").strip() or "Non renseignée" for row in metric_rows)
    commercial_counter = Counter(row.commercial_id for row in metric_rows)
    evolution_counter = Counter(row.date.isoformat() for row in metric_rows if row.date)

    commercials = (
        User.query.filter_by(role="commercial")
        .order_by(User.username)
        .all()
    )
    zones = [z for (z,) in Prospection.query.with_entities(Prospection.zone).distinct().order_by(Prospection.zone).all() if z]
    regions = [r for (r,) in Prospection.query.with_entities(Prospection.region).distinct().order_by(Prospection.region).all() if r]
    specialites = [
        s
        for (s,) in Prospection.query.with_entities(Prospection.specialite)
        .distinct()
        .order_by(Prospection.specialite)
        .all()
        if s
    ]

    visit_targets = _visit_targets_for_commercials(commercials)
    objectifs = []
    for commercial in commercials:
        if commercial_id and commercial.id != commercial_id:
            continue
        realise = commercial_counter.get(commercial.id, 0)
        activity_target = visit_targets.get(commercial.id, 100)
        taux = round(realise * 100 / activity_target, 1) if activity_target else 0
        if taux >= 100:
            statut, badge = "Objectif atteint", "bg-success"
        elif taux >= 80:
            statut, badge = "À surveiller", "bg-warning text-dark"
        else:
            statut, badge = "Insuffisant", "bg-danger"
        objectifs.append(
            {
                "name": commercial.username,
                "commercial_id": commercial.id,
                "objectif": activity_target,
                "realise": realise,
                "taux": taux,
                "statut": statut,
                "badge": badge,
            }
        )

    commercial_chart_rows = [
        (cid, count)
        for cid, count in commercial_counter.most_common()
    ]
    charts = {
        "specialites": {
            "labels": list(specialites_counter.keys()),
            "values": list(specialites_counter.values()),
        },
        "zones": {"labels": list(zones_counter.keys()), "values": list(zones_counter.values())},
        "regions": {"labels": list(regions_counter.keys()), "values": list(regions_counter.values())},
        "commercials": {
            "labels": [
                next(
                    (c.username for c in commercials if c.id == cid),
                    str(cid),
                )
                for cid, _ in commercial_chart_rows
            ],
            "values": [count for _, count in commercial_chart_rows],
        },
        "evolution": {
            "labels": [label for label, _ in sorted(evolution_counter.items())],
            "values": [count for _, count in sorted(evolution_counter.items())],
        },
    }

    kpis = [
        {"label": "Prospections", "value": total_prospections},
        {"label": "Professionnels", "value": len(professionals)},
        {"label": "Structures", "value": len(structures)},
        {"label": "Zones couvertes", "value": len({k for k in zones_counter if k != "Non renseignée"})},
        {"label": "Régions couvertes", "value": len({k for k in regions_counter if k != "Non renseignée"})},
    ]

    # V3.5 : tableau de pilotage par visiteur médical + alertes.
    visitor_rows = []
    for commercial in commercials:
        own_rows = [row for row in metric_rows if row.commercial_id == commercial.id]
        own_professionals = {professional_key(row) for row in own_rows if professional_key(row)}
        own_structures = {_normalize_text(row.establishment or row.nom_client) for row in own_rows if _normalize_text(row.establishment or row.nom_client)}
        own_zones = {(row.zone or "").strip() for row in own_rows if (row.zone or "").strip()}
        own_regions = {(row.region or "").strip() for row in own_rows if (row.region or "").strip()}
        visitor_rows.append({
            "commercial_id": commercial.id,
            "name": commercial.username,
            "prospections": len(own_rows),
            "professionals": len(own_professionals),
            "structures": len(own_structures),
            "zones": len(own_zones),
            "regions": len(own_regions),
        })

    alert_query = query.with_entities(
        Prospection.id,
        Prospection.date,
        Prospection.commercial_id,
        Prospection.nom_client,
        Prospection.establishment,
        Prospection.zone,
        Prospection.region,
        Prospection.planning_id,
        Prospection.a_revoir,
        Prospection.date_relance,
    ).all()
    hors_planning_count = sum(1 for row in alert_query if row.planning_id is None)
    missing_geo_count = sum(1 for row in alert_query if not (row.zone or "").strip() or not (row.region or "").strip())
    overdue_relances = sum(1 for row in alert_query if row.a_revoir and row.date_relance and row.date_relance < date.today())
    active_ids = {c.id for c in commercials if c.is_active_account}
    activity_ids = {row.commercial_id for row in metric_rows}
    inactive_visitors = [c.username for c in commercials if c.id in active_ids and c.id not in activity_ids]
    alerts = [
        {"type": "danger", "label": "Relances en retard", "value": overdue_relances, "detail": "Prospections avec une date de relance dépassée."},
        {"type": "warning", "label": "Prospections hors planning", "value": hors_planning_count, "detail": "Prospections réalisées sans rattachement à une ligne de planning."},
        {"type": "warning", "label": "Géographie incomplète", "value": missing_geo_count, "detail": "Prospections sans zone ou région renseignée."},
        {"type": "info", "label": "Visiteurs sans activité", "value": len(inactive_visitors), "detail": ", ".join(inactive_visitors[:8]) if inactive_visitors else "Tous les visiteurs actifs ont au moins une prospection dans la période."},
    ]

    return render_template(
        "dashboard_direction.html",
        kpis=kpis,
        charts=charts,
        objectifs=objectifs,
        commercials=commercials,
        commerciaux=commercials,
        visitor_rows=visitor_rows,
        alerts=alerts,
        zones=zones,
        specialites=specialites,
        filters={
            "date_start": date_start_raw,
            "date_end": date_end_raw,
            "commercial_id": commercial_raw,
            "zone": zone,
            "region": region,
            "specialite": specialite,
        },
    )
