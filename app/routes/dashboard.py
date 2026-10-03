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