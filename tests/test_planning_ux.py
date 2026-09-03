from pathlib import Path


TEMPLATE = Path(__file__).resolve().parents[1] / "app" / "templates" / "admin_plannings.html"


def test_planning_generation_form_has_ux_defaults_and_guards():
    content = TEMPLATE.read_text(encoding="utf-8")

    assert "data-start-date" in content
    assert "Prérempli sur le prochain lundi." in content
    assert "data-visits-preset=\"5\"" in content
    assert "data-visits-preset=\"10\"" in content
    assert "day === 0 || day === 6" in content
    assert "window.confirm('Générer un nouveau cycle de 4 semaines" in content
