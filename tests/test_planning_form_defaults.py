from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "app" / "routes" / "planning.py"
TEMPLATE = ROOT / "app" / "templates" / "saisie_planning.html"


def test_new_planning_defaults_to_next_monday_only_on_initial_get():
    content = ROUTE.read_text(encoding="utf-8")

    assert "def _next_monday(reference=None):" in content
    assert "if request.method == \"GET\" and formulaire.date.data is None:" in content
    assert "formulaire.date.data = _next_monday()" in content


def test_planning_form_keeps_all_seven_days_and_mobile_layout():
    content = TEMPLATE.read_text(encoding="utf-8")

    for day in ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"):
        assert "('" + day + "'" in content
    assert "closeOnSelect: false" in content
    assert "@media (max-width: 760px)" in content
    assert "grid-template-columns: minmax(0, 1fr)" in content
