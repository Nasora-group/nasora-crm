from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "app" / "routes" / "planning.py"
CARD = ROOT / "app" / "templates" / "_planning_week_card.html"


def test_weekly_duplication_is_post_only_and_csrf_protected():
    content = ROUTE.read_text(encoding="utf-8")

    assert '@planning_bp.route("/planning/<int:planning_id>/dupliquer", methods=["POST"])' in content
    assert 'form = CSRFOnlyForm()' in content
    assert 'if not form.validate_on_submit():' in content


def test_weekly_duplication_checks_ownership_and_never_overwrites_target_week():
    content = ROUTE.read_text(encoding="utf-8")

    assert "if not owns_record(current_user, planning):" in content
    assert "target_date = planning.date + timedelta(days=7)" in content
    assert "if existing is not None:" in content
    assert "Le planning existant reste intact." in content


def test_weekly_duplication_copies_all_seven_days_and_keeps_source():
    content = ROUTE.read_text(encoding="utf-8")
    card = CARD.read_text(encoding="utf-8")

    assert "**{day: getattr(planning, day) for day in JOURS}" in content
    duplicate_handler = content.split("def duplicate_planning(planning_id):", 1)[1].split("def delete_planning(planning_id):", 1)[0]
    assert "db.session.delete(planning)" not in duplicate_handler
    assert "planning.duplicate_planning" in card
    assert "Dupliquer la semaine" in card
