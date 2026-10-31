from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage

from app.routes.animation_sales import _read_animation_evidence


def _file(name, mime, data):
    return FileStorage(stream=BytesIO(data), filename=name, content_type=mime)


def test_animation_evidence_accepts_jpeg():
    evidence = _read_animation_evidence(
        _file("animation.jpg", "image/jpeg", b"\xff\xd8\xff" + b"photo")
    )
    assert evidence["filename"] == "animation.jpg"
    assert evidence["mime_type"] == "image/jpeg"
    assert evidence["file_size"] == 8


def test_animation_evidence_rejects_non_image():
    with pytest.raises(ValueError, match="JPG, PNG ou WEBP"):
        _read_animation_evidence(
            _file("animation.pdf", "application/pdf", b"%PDF-1.7")
        )


def test_animation_evidence_rejects_oversized_file():
    with pytest.raises(ValueError, match="5 Mo"):
        _read_animation_evidence(
            _file("animation.jpg", "image/jpeg", b"\xff\xd8\xff" + b"x" * (5 * 1024 * 1024))
        )


def test_animation_evidence_allows_commercial_only_in_their_division():
    from pathlib import Path

    route = Path(__file__).resolve().parents[1] / "app" / "routes" / "animation_sales.py"
    content = route.read_text(encoding="utf-8")
    evidence_route = content.split('def animation_evidence(evidence_id):', 1)[1].split('@animation_sales_bp.route("/animateur/', 1)[0]

    assert '@roles_required("admin", "commercial", "animateur")' in content
    assert 'current_user.role == "commercial" and not division_matches(current_user, evidence.project)' in evidence_route
    assert 'current_user.role == "animateur" and evidence.animateur_id != current_user.id' in evidence_route
