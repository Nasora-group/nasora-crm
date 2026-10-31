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


def test_prospection_creation_commits_before_admin_notification():
    content = ROUTE.read_text(encoding="utf-8")
    create_block = content.split('def index():', 1)[1].split('@dashboard_bp.route("/dashboard/prospections"', 1)[0]

    commit_position = create_block.index("db.session.commit()")
    notification_position = create_block.index("notify_admins(")
    assert commit_position < notification_position
    assert "except Exception:" in create_block[notification_position:]
    assert "Prospection enregistrée, mais notification administrateur impossible." in create_block


def test_prospection_edit_commits_before_admin_notification():
    content = ROUTE.read_text(encoding="utf-8")
    edit_block = content.split("def edit_prospection(prospection_id):", 1)[1].split('@dashboard_bp.route("/dashboard/prospection/<int:prospection_id>/supprimer"', 1)[0]

    commit_position = edit_block.index("db.session.commit()")
    notification_position = edit_block.index("notify_admins(")
    assert commit_position < notification_position
    assert "except Exception:" in edit_block[notification_position:]
    assert "Prospection modifiée, mais notification administrateur impossible." in edit_block
