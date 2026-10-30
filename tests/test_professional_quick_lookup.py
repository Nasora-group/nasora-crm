from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "app" / "routes" / "dashboard.py"
TEMPLATE = ROOT / "app" / "templates" / "dashboard.html"


def test_professional_suggestions_are_scoped_to_owner_and_shared_records():
    content = ROUTE.read_text(encoding="utf-8")

    assert "quick_clients = (" in content
    assert "Client.owner_id.is_(None)" in content
    assert "Client.owner_id == current_user.id" in content
    assert ".limit(150)" in content
    assert "quick_clients=quick_clients" in content


def test_prospection_form_offers_existing_professionals_and_autofills_details():
    content = TEMPLATE.read_text(encoding="utf-8")

    assert 'list="nasora-professionals"' in content
    assert 'id="nasora-professionals"' in content
    assert 'data-specialty="{{ client.specialty or \'\' }}"' in content
    assert 'data-phone="{{ client.phone or \'\' }}"' in content
    assert "professionalInput.addEventListener('change'" in content
    assert "data.address" in content
    assert "data.region" in content
