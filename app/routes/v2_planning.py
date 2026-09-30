from datetime import date, timedelta
import re
import unicodedata

from flask import Blueprint, render_template, request
from flask_login import login_required

from app.models import Planning, Prospection, User, JOURS
from app.models_clients import ClientVisit
from app.permissions import is_admin
from app.utils import decode_planning_slot

v2_planning_bp = Blueprint("v2_planning", __name__, url_prefix="/v2/planning")


def _norm(value):
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def _date(value, fallback):
    try:
        return date.fromisoformat(value) if value else fallback
    except ValueError:
        return fallback


def _monday(value):
    return value - timedelta(days=value.weekday())


def _week_days(start):
    return [start + timedelta(days=i) for i in range(5)]


def _planned_slots(planning):
    rows = []
    for day_name in JOURS[:5]:
        current_date = planning.date + timedelta(days=JOURS[:5].index(day_name))
        for structure_type, name in decode_planning_slot(getattr(planning, day_name)):
            rows.append({
                "date": current_date,
                "day": day_name,
                "structure": structure_type,
                "name": (name or "").strip(),
            })
    return rows


def _actual_by_date(commercial_id, start, end):
    visits = (
        ClientVisit.query
        .filter(
            ClientVisit.commercial_id == commercial_id,
            ClientVisit.date >= start,
            ClientVisit.date <= end,
            ClientVisit.is_duplicate.is_(False),
        )
        .all()
    )
    prospections = (
        Prospection.query
        .filter(
            Prospection.commercial_id == commercial_id,
            Prospection.date >= start,
            Prospection.date <= end,
        )
        .all()
    )
    by_date = {}
    for visit in visits:
        name = visit.client.name if visit.client else ""
        establishment = visit.client.establishment if visit.client else ""
        by_date.setdefault(visit.date, []).append({
            "name": name,
            "establishment": establishment,
            "structure": visit.client.structure if visit.client else "",
            "source": "Visite CRM",
            "id": visit.id,
        })
    for prospect in prospections:
        name = prospect.establishment or prospect.nom_client or ""
        by_date.setdefault(prospect.date, []).append({
            "name": name,
            "establishment": prospect.establishment or "",
            "structure": prospect.structure or "",
            "source": "Prospection",
            "id": prospect.id,
        })
    return by_date


def _match(planned, actual):
    target = _norm(planned["name"])
    if not target:
        return False
    candidates = {_norm(actual.get("name")), _norm(actual.get("establishment"))}
    if target in candidates:
        return True
    for candidate in candidates:
        if candidate and (target in candidate or candidate in target):
            return True
    return False


@v2_planning_bp.route("")
@login_required
def index():
    if not is_admin():
        return render_template("403.html"), 403

    today = date.today()
    default_start = _monday(today - timedelta(days=28))
    default_end = _monday(today)
    start = _monday(_date(request.args.get("date_start"), default_start))
    end = _monday(_date(request.args.get("date_end"), default_end))
    if end < start:
        start, end = end, start

    division = (request.args.get("division") or "all").strip().lower()
    user_id = request.args.get("user_id", type=int)

    users_query = User.query.filter(
        User.role.in_(("commercial", "animateur")),
        User.is_active_account.is_(True),
    )
    if division in ("nasmedic", "nasderm"):
        users_query = users_query.filter(User.project.ilike(division))
    users = users_query.order_by(User.username).all()

    selected_users = users
    if user_id:
        selected_users = [u for u in users if u.id == user_id]

    rows = []
    total_planned = total_realized = 0

    cursor = start
    while cursor <= end:
        week_end = cursor + timedelta(days=4)
        for user in selected_users:
            planning = (
                Planning.query
                .filter_by(commercial_id=user.id, date=cursor)
                .first()
            )
            planned = _planned_slots(planning) if planning else []
            actual = _actual_by_date(user.id, cursor, week_end)
            consumed = set()
            for item in planned:
                matches = actual.get(item["date"], [])
                matched = next((a for a in matches if a["id"] not in consumed and _match(item, a)), None)
                if matched:
                    consumed.add(matched["id"])
                item["user"] = user
                item["realized"] = bool(matched)
                item["actual"] = matched
                rows.append(item)
                total_planned += 1
                total_realized += int(bool(matched))
            if not planned:
                rows.append({
                    "date": cursor,
                    "day": "",
                    "structure": "",
                    "name": "",
                    "user": user,
                    "realized": False,
                    "actual": None,
                    "empty_week": True,
                })
        cursor += timedelta(days=7)

    # Rebuild weekly summaries from the planned rows.
    summaries = {}
    for item in rows:
        if item.get("empty_week"):
            continue
        week = _monday(item["date"])
        key = (week, item["user"].id)
        summary = summaries.setdefault(key, {
            "week": week,
            "user": item["user"],
            "planned": 0,
            "realized": 0,
            "missed": 0,
        })
        summary["planned"] += 1
        summary["realized"] += int(item["realized"])
        summary["missed"] += int(not item["realized"])

    summary_rows = sorted(summaries.values(), key=lambda x: (x["week"], x["user"].username), reverse=True)
    for item in summary_rows:
        item["rate"] = round((item["realized"] / item["planned"]) * 100, 1) if item["planned"] else 0

    for item in rows:
        if "date" in item:
            item["date_label"] = item["date"].strftime("%d/%m/%Y")

    return render_template(
        "v2/planning.html",
        rows=rows,
        summaries=summary_rows,
        users=users,
        total_planned=total_planned,
        total_realized=total_realized,
        completion_rate=round((total_realized / total_planned) * 100, 1) if total_planned else 0,
        date_start=start,
        date_end=end,
        division=division,
        user_id=user_id,
    )
