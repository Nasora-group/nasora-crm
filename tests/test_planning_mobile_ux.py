from datetime import date
from pathlib import Path

from app.routes.planning import _next_monday


ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "app" / "routes" / "planning.py"
TEMPLATE = ROOT / "app" / "templates" / "saisie_planning.html"


def test_next_monday_returns_monday_for_weekday_reference():
    assert _next_monday(date(2026, 10, 21)) == date(2026, 10, 26)


def test_next_monday_keeps_reference_when_it_is_monday():
    assert _next_monday(date(2026, 10, 26)) == date(2026, 10, 26)


def test_planning_creation_prefills_date_only_on_initial_get():
    content = ROUTE.read_text(encoding="utf-8")

    assert 'if request.method == "GET" and formulaire.date.data is None:' in content
    assert "formulaire.date.data = _next_monday()" in content


def test_planning_form_has_mobile_first_layout_and_large_touch_targets():
    content = TEMPLATE.read_text(encoding="utf-8")

    assert "@media (max-width: 760px)" in content
    assert "grid-template-columns: minmax(0, 1fr)" in content
    assert "min-height: 52px" in content
    assert "input.required = true" in content
    assert "Renseigne le nom précis de chaque structure sélectionnée" in content


def test_planning_form_keeps_all_seven_days():
    content = TEMPLATE.read_text(encoding="utf-8")

    for day in ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"):
        assert "('" + day + "'" in content


def test_planning_form_caches_names_when_a_structure_is_deselected_and_reselected():
    content = TEMPLATE.read_text(encoding="utf-8")

    assert "selectEl._planningNameCache" in content
    assert "nameCache[structure] = input.value" in content
    assert "nameCache[value] = input.value" in content
    assert "nameCache[value]" in content


def test_planning_form_has_save_action_near_top_and_bottom():
    content = TEMPLATE.read_text(encoding="utf-8")

    assert content.count('class="btn-submit"') >= 2
    assert 'class="form-group planning-top-actions"' in content
    assert "Enregistrer le planning" in content
