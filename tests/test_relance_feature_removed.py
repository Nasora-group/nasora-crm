from pathlib import Path

from app.forms import ProspectionForm
from app.models import Prospection


def test_prospection_form_no_longer_exposes_relance_fields():
    form = ProspectionForm()

    assert "a_revoir" not in form._fields
    assert "date_relance" not in form._fields
    assert "motif_relance" not in form._fields


def test_relance_columns_are_retained_to_preserve_existing_data():
    # The feature is removed from the application UI, but historical values
    # remain in the database model until a separately approved data migration.
    assert hasattr(Prospection, "a_revoir")
    assert hasattr(Prospection, "date_relance")
    assert hasattr(Prospection, "motif_relance")


def test_relance_controls_are_absent_from_prospection_and_professional_pages():
    root = Path(__file__).resolve().parents[1] / "app" / "templates"
    templates = [
        root / "dashboard.html",
        root / "edit_prospection.html",
        root / "client_detail.html",
    ]

    for template in templates:
        content = template.read_text(encoding="utf-8").lower()
        assert "suivi et relance" not in content
        assert "date_relance" not in content
        assert "a_revoir" not in content
