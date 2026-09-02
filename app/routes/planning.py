from datetime import date, timedelta

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms import PlanningForm, CSRFOnlyForm
from app.models import Planning, Prospection, User, JOURS, STRUCTURE_SLUGS
from app.services.planning_ai import PlanningCandidate, generate_two_weeks, planning_entries_for_week
from app.utils import roles_required, encode_planning_slot, decode_planning_slot

planning_bp = Blueprint("planning", __name__)

WORKING_DAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi")
NON_WORKING_DAYS = ("samedi", "dimanche")


def _build_creneaux_from_form():
    """Lit les structures sélectionnées et force samedi/dimanche à rester vides."""
    creneaux = {}
    empty_slot = encode_planning_slot([])
    for jour in JOURS:
        if jour in NON_WORKING_DAYS:
            creneaux[jour] = empty_slot
            continue

        structures_selectionnees = request.form.getlist(jour)
        entries = []
        for structure in structures_selectionnees:
            slug = STRUCTURE_SLUGS.get(structure, structure.replace(" ", "_"))
            nom = request.form.get(f"{jour}_nom__{slug}", "")
            entries.append((structure, nom))
        creneaux[jour] = encode_planning_slot(entries)
    return creneaux


def _valid_week_start(value):
    """Return whether a planning week starts on a Monday."""
    return value is not None and value.weekday() == 0


def _next_monday(reference=None):
    reference = reference or date.today()
    return reference + timedelta(days=(7 - reference.weekday()) % 7)


def _cycle_dates(start_date):
    """Return the four Monday dates covered by a generated cycle."""
    if not _valid_week_start(start_date):
        raise ValueError("La date de début doit être un lundi")
    return [start_date + timedelta(days=7 * index) for index in range(4)]


def _cycle_already_exists(commercial_id, cycle_dates, lock=False):
    """Return whether this commercial already has any planning in the cycle."""
    query = Planning.query.filter(
        Planning.commercial_id == commercial_id,
        Planning.date.in_(cycle_dates),
    )
    if lock:
        query = query.with_for_update()
    return query.first() is not None


def _planning_date_already_exists(commercial_id, planning_date, exclude_id=None, lock=False, query=None):
    """Return whether a commercial already has a planning for a given Monday."""
    query = query or Planning.query
    query = query.filter(
        Planning.commercial_id == commercial_id,
        Planning.date == planning_date,
    )
    if exclude_id is not None:
        query = query.filter(Planning.id != exclude_id)
    if lock:
        query = query.with_for_update()
    return query.first() is not None


def _planning_candidates(commercial_id):
    """Build candidates only from real establishments already entered by this commercial."""
    rows = (
        Prospection.query.filter_by(commercial_id=commercial_id)
        .order_by(Prospection.date.desc(), Prospection.id.desc())
        .all()
    )
    latest = {}
    for row in rows:
        name = (row.establishment or row.nom_client or "").strip()
        structure = (row.structure or "").strip()
        if not name or not structure:
            continue
        key = (structure.upper(), name.casefold())
        if key not in latest:
            latest[key] = PlanningCandidate(structure=structure, name=name, last_visit=row.date)
    return list(latest.values())


def _monday_plannings(query):
    """Keep only legitimate Monday-start planning rows without DB-specific SQL."""
    return [planning for planning in query.all() if planning.date and planning.date.weekday() == 0]


@planning_bp.route("/visualiser_planning")
@login_required
@roles_required("commercial")
def visualiser():
    # A valid planning always starts on Monday. Exclude legacy/non-conforming
    # rows from the commercial view so Saturday/Sunday can never reappear as
    # a planning week after older data or a manual DB import.
    plannings = _monday_plannings(
        Planning.query.filter_by(commercial_id=current_user.id).order_by(Planning.date.desc())
    )
    delete_form = CSRFOnlyForm()
    return render_template("visualiser_planning.html", plannings=plannings, delete_form=delete_form)


@planning_bp.route("/saisie_planning", methods=["GET", "POST"])
@login_required
@roles_required("commercial")
def saisie():
    formulaire = PlanningForm()

    if formulaire.validate_on_submit():
        if not _valid_week_start(formulaire.date.data):
            flash("La date de début doit être un lundi.", "error")
            return render_template("saisie_planning.html", formulaire=formulaire, mode="create", existing_types={}, existing_details={})

        # Serialize manual creations for the same commercial. The database
        # row lock prevents two simultaneous requests from both passing the
        # duplicate-week check before either one inserts its planning.
        User.query.filter_by(id=current_user.id).with_for_update().first()
        if _planning_date_already_exists(current_user.id, formulaire.date.data, lock=True):
            db.session.rollback()
            flash("Un planning existe déjà pour cette semaine.", "error")
            return render_template("saisie_planning.html", formulaire=formulaire, mode="create", existing_types={}, existing_details={})

        nouveau_planning = Planning(
            commercial_id=current_user.id,
            date=formulaire.date.data,
            **_build_creneaux_from_form(),
        )
        db.session.add(nouveau_planning)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Impossible d'enregistrer le planning : il existe déjà pour cette semaine.", "error")
            return render_template("saisie_planning.html", formulaire=formulaire, mode="create", existing_types={}, existing_details={})
        flash("Planning enregistré avec succès.", "success")
        return redirect(url_for("planning.visualiser"))

    return render_template("saisie_planning.html", formulaire=formulaire, mode="create", existing_types={}, existing_details={})


@planning_bp.route("/planning/<int:planning_id>/modifier", methods=["GET", "POST"])
@login_required
@roles_required("commercial")
def edit_planning(planning_id):
    planning = Planning.query.get_or_404(planning_id)
    if planning.commercial_id != current_user.id:
        flash("Accès non autorisé : ce planning ne t'appartient pas.", "error")
        return render_template("403.html"), 403

    formulaire = PlanningForm(obj=planning)

    if formulaire.validate_on_submit():
        if not _valid_week_start(formulaire.date.data):
            flash("La date de début doit être un lundi.", "error")
            return render_template(
                "saisie_planning.html",
                formulaire=formulaire,
                mode="edit",
                planning=planning,
                existing_types={jour: [t for t, _n in decode_planning_slot(getattr(planning, jour))] for jour in JOURS},
                existing_details={jour: {t: n for t, n in decode_planning_slot(getattr(planning, jour))} for jour in JOURS},
            )

        # Lock the commercial row before checking the target week so two
        # simultaneous edits cannot both move planning onto the same Monday.
        User.query.filter_by(id=current_user.id).with_for_update().first()
        if _planning_date_already_exists(current_user.id, formulaire.date.data, exclude_id=planning.id, lock=True):
            db.session.rollback()
            flash("Un planning existe déjà pour cette semaine.", "error")
            return render_template(
                "saisie_planning.html",
                formulaire=formulaire,
                mode="edit",
                planning=planning,
                existing_types={jour: [t for t, _n in decode_planning_slot(getattr(planning, jour))] for jour in JOURS},
                existing_details={jour: {t: n for t, n in decode_planning_slot(getattr(planning, jour))} for jour in JOURS},
            )

        planning.date = formulaire.date.data
        for champ, valeur in _build_creneaux_from_form().items():
            setattr(planning, champ, valeur)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Impossible de mettre à jour le planning : cette semaine est déjà occupée.", "error")
            return render_template(
                "saisie_planning.html",
                formulaire=formulaire,
                mode="edit",
                planning=planning,
                existing_types={jour: [t for t, _n in decode_planning_slot(getattr(planning, jour))] for jour in JOURS},
                existing_details={jour: {t: n for t, n in decode_planning_slot(getattr(planning, jour))} for jour in JOURS},
            )
        flash("Planning mis à jour avec succès.", "success")
        return redirect(url_for("planning.visualiser"))

    existing_types = {}
    existing_details = {}
    for jour in JOURS:
        entries = decode_planning_slot(getattr(planning, jour))
        existing_types[jour] = [t for t, _n in entries]
        existing_details[jour] = {t: n for t, n in entries}

    return render_template(
        "saisie_planning.html",
        formulaire=formulaire,
        mode="edit",
        planning=planning,
        existing_types=existing_types,
        existing_details=existing_details,
    )


@planning_bp.route("/planning/<int:planning_id>/supprimer", methods=["POST"])
@login_required
@roles_required("commercial")
def delete_planning(planning_id):
    form = CSRFOnlyForm()
    planning = Planning.query.get_or_404(planning_id)

    if planning.commercial_id != current_user.id:
        flash("Accès non autorisé : ce planning ne t'appartient pas.", "error")
        return redirect(url_for("planning.visualiser"))

    if form.validate_on_submit():
        db.session.delete(planning)
        db.session.commit()
        flash("Planning supprimé.", "success")

    return redirect(url_for("planning.visualiser"))


@planning_bp.route("/admin_plannings")
@login_required
@roles_required("admin")
def admin_plannings():
    commerciaux = User.query.filter_by(role="commercial").order_by(User.username).all()
    return render_template("admin_plannings.html", commerciaux=commerciaux)


@planning_bp.route("/admin_planning_detail/<int:commercial_id>")
@login_required
@roles_required("admin")
def admin_planning_detail(commercial_id):
    commercial = User.query.get_or_404(commercial_id)
    # Only Monday-start rows are legitimate planning weeks. This also keeps
    # legacy weekend/non-Monday rows out of the admin presentation.
    plannings = _monday_plannings(
        Planning.query.filter_by(commercial_id=commercial_id).order_by(Planning.date.desc())
    )
    return render_template("admin_planning_detail.html", plannings=plannings, commercial=commercial)


@planning_bp.route("/admin_planning_generate/<int:commercial_id>", methods=["POST"])
@login_required
@roles_required("admin")
def admin_planning_generate(commercial_id):
    commercial = User.query.get_or_404(commercial_id)
    try:
        visits_per_day = int(request.form.get("visits_per_day", "5"))
    except ValueError:
        visits_per_day = 5
    if not 1 <= visits_per_day <= 20:
        flash("Le nombre de visites par jour doit être compris entre 1 et 20.", "error")
        return redirect(url_for("planning.admin_plannings"))

    start_raw = request.form.get("start_date", "").strip()
    try:
        start_date = date.fromisoformat(start_raw) if start_raw else _next_monday()
    except ValueError:
        flash("Date de début invalide.", "error")
        return redirect(url_for("planning.admin_plannings"))
    if not _valid_week_start(start_date):
        flash("La date de début doit être un lundi.", "error")
        return redirect(url_for("planning.admin_plannings"))

    candidates = _planning_candidates(commercial.id)
    try:
        weeks = generate_two_weeks(candidates, start_date, visits_per_day=visits_per_day)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("planning.admin_plannings"))

    cycle_dates = _cycle_dates(start_date)
    if _cycle_already_exists(commercial.id, cycle_dates):
        flash("Génération annulée : un planning existe déjà sur l'une des quatre semaines.", "error")
        return redirect(url_for("planning.admin_planning_detail", commercial_id=commercial.id))

    generated_entries = [planning_entries_for_week(week) for week in weeks]
    complete_cycle = generated_entries + [generated_entries[0], generated_entries[1]]
    empty_slot = encode_planning_slot([])

    # Lock the commercial row for the transaction so two concurrent generations
    # for the same commercial cannot both pass the overlap check before insert.
    try:
        User.query.filter_by(id=commercial.id).with_for_update().first()
        if _cycle_already_exists(commercial.id, cycle_dates, lock=True):
            db.session.rollback()
            flash("Génération annulée : un planning existe déjà sur l'une des quatre semaines.", "error")
            return redirect(url_for("planning.admin_planning_detail", commercial_id=commercial.id))

        for cycle_index, cycle_date in enumerate(cycle_dates):
            fields = {jour: encode_planning_slot(complete_cycle[cycle_index][jour]) for jour in WORKING_DAYS}
            fields.update({jour: empty_slot for jour in NON_WORKING_DAYS})
            db.session.add(Planning(commercial_id=commercial.id, date=cycle_date, **fields))

        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Génération annulée : le planning existe déjà ou ne peut pas être créé.", "error")
        return redirect(url_for("planning.admin_planning_detail", commercial_id=commercial.id))

    flash(
        f"Cycle de 4 semaines généré pour {commercial.username} : S1/S2 créées, S3=S1 et S4=S2.",
        "success",
    )
    return redirect(url_for("planning.admin_planning_detail", commercial_id=commercial.id))
