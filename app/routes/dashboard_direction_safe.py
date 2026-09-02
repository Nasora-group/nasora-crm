import logging
from collections import Counter
from datetime import date

from flask import Blueprint, render_template, request
from flask_login import login_required

from app.models import Prospection, User
from app.utils import roles_required
from app.visit_metrics import professional_key
from app.routes.dashboard import _normalize_text
from app.visit_objectives_readonly import read_visit_targets

logger = logging.getLogger(__name__)
terrain_bp = Blueprint("dashboard_safe", __name__)


@terrain_bp.route("/admin/dashboard-direction", methods=["GET"])
@login_required
@roles_required("admin")
def direction():
    """Safe, read-only rendering of the Direction terrain dashboard.

    This route deliberately avoids lazy relationship access and any schema
    creation during page rendering. It keeps Prospection as the source of
    truth and falls back cleanly when optional data is unavailable.
    """
    try:
        date_start_raw = (request.args.get("date_start") or "").strip()
        date_end_raw = (request.args.get("date_end") or "").strip()
        commercial_raw = (request.args.get("commercial_id") or "").strip()
        zone = (request.args.get("zone") or "").strip()
        specialite = (request.args.get("specialite") or "").strip()

        def parse_date(value):
            try:
                return date.fromisoformat(value) if value else None
            except (TypeError, ValueError):
                return None

        date_start = parse_date(date_start_raw)
        date_end = parse_date(date_end_raw)
        commercial_id = int(commercial_raw) if commercial_raw.isdigit() else None

        commercials = User.query.filter_by(role="commercial").order_by(User.username).all()
        commercial_by_id = {c.id: c for c in commercials}

        query = Prospection.query.filter(Prospection.commercial_id.in_(commercial_by_id.keys()))
        if date_start:
            query = query.filter(Prospection.date >= date_start)
        if date_end:
            query = query.filter(Prospection.date <= date_end)
        if commercial_id:
            query = query.filter(Prospection.commercial_id == commercial_id)
        if zone:
            query = query.filter(Prospection.commercial_id.in_([c.id for c in commercials if (c.zone or "") == zone]))
        if specialite:
            query = query.filter(Prospection.specialite == specialite)

        rows = query.order_by(Prospection.date.asc(), Prospection.id.asc()).all()
        total_prospections = len(rows)
        professionals = {key for row in rows if (key := professional_key(row))}
        structures = {
            (_normalize_text(getattr(row, "establishment", None) or getattr(row, "structure", None) or row.nom_client), row.commercial_id)
            for row in rows
            if _normalize_text(getattr(row, "establishment", None) or getattr(row, "structure", None) or row.nom_client)
        }

        specialites_counter = Counter((row.specialite or "Non renseignée").strip() or "Non renseignée" for row in rows)
        zones_counter = Counter((commercial_by_id.get(row.commercial_id).zone if commercial_by_id.get(row.commercial_id) else None) or "Non renseignée" for row in rows)
        commercial_counter = Counter(row.commercial_id for row in rows)
        evolution_counter = Counter(row.date.isoformat() for row in rows if row.date)

        zones = sorted({(c.zone or "").strip() for c in commercials if (c.zone or "").strip()})
        specialites = sorted({(row.specialite or "").strip() for row in Prospection.query.with_entities(Prospection.specialite).all() if row[0] and row[0].strip()})

        try:
            visit_targets = read_visit_targets(commercials)
        except Exception:
            logger.exception("Impossible de charger les objectifs de visites")
            visit_targets = {c.id: 100 for c in commercials}

        objectifs = []
        for commercial in commercials:
            if commercial_id and commercial.id != commercial_id:
                continue
            realise = commercial_counter.get(commercial.id, 0)
            target = int(visit_targets.get(commercial.id, 100) or 0)
            taux = round(realise * 100 / target, 1) if target else 0
            if taux >= 100:
                statut, badge = "Objectif atteint", "bg-success"
            elif taux >= 80:
                statut, badge = "À surveiller", "bg-warning text-dark"
            else:
                statut, badge = "Insuffisant", "bg-danger"
            objectifs.append({"commercial_id": commercial.id, "name": commercial.username, "objectif": target, "realise": realise, "taux": taux, "statut": statut, "badge": badge})

        ordered_evolution = sorted(evolution_counter.items())
        top_commercials = commercial_counter.most_common()
        charts = {
            "specialites": {"labels": list(specialites_counter.keys()), "values": list(specialites_counter.values())},
            "zones": {"labels": list(zones_counter.keys()), "values": list(zones_counter.values())},
            "commercials": {
                "labels": [commercial_by_id[cid].username if cid in commercial_by_id else str(cid) for cid, _ in top_commercials],
                "values": [count for _, count in top_commercials],
            },
            "evolution": {"labels": [label for label, _ in ordered_evolution], "values": [count for _, count in ordered_evolution]},
        }
        kpis = [
            {"label": "Prospections", "value": total_prospections},
            {"label": "Professionnels visités", "value": len(professionals)},
            {"label": "Structures visitées", "value": len(structures)},
            {"label": "Commerciaux actifs", "value": len([c for c in commercials if c.is_active_account])},
        ]
        filters = {
            "date_start": date_start_raw,
            "date_end": date_end_raw,
            "commercial_id": commercial_raw,
            "zone": zone,
            "specialite": specialite,
        }
        return render_template("dashboard_direction.html", kpis=kpis, charts=charts, objectifs=objectifs, commercials=commercials, zones=zones, specialites=specialites, filters=filters)
    except Exception:
        logger.exception("Erreur sécurisée lors du chargement de l'Activité terrain")
        empty_charts = {"specialites": {"labels": [], "values": []}, "zones": {"labels": [], "values": []}, "commercials": {"labels": [], "values": []}, "evolution": {"labels": [], "values": []}}
        filters = {"date_start": request.args.get("date_start", ""), "date_end": request.args.get("date_end", ""), "commercial_id": request.args.get("commercial_id", ""), "zone": request.args.get("zone", ""), "specialite": request.args.get("specialite", "")}
        return render_template("dashboard_direction.html", kpis=[{"label": "Prospections", "value": 0}, {"label": "Professionnels visités", "value": 0}, {"label": "Structures visitées", "value": 0}, {"label": "Commerciaux actifs", "value": 0}], charts=empty_charts, objectifs=[], commercials=[], zones=[], specialites=[], filters=filters)
