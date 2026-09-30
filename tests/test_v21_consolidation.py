from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage

from app.routes.v2_animations import _validate_image_upload


def _file(name, mime, data):
    return FileStorage(stream=BytesIO(data), filename=name, content_type=mime)


def test_v21_image_validation_accepts_real_jpeg():
    filename, mime = _validate_image_upload(
        _file("animation.jpg", "image/jpeg", b"\xff\xd8\xff" + b"photo"),
        b"\xff\xd8\xff" + b"photo",
    )
    assert filename == "animation.jpg"
    assert mime == "image/jpeg"


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("animation.pdf", b"%PDF-1.7"),
        ("animation.svg", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"),
        ("animation.jpg", b"not-an-image"),
    ],
)
def test_v21_image_validation_rejects_non_images(name, data):
    with pytest.raises(ValueError, match="JPEG, PNG ou WebP"):
        _validate_image_upload(_file(name, "image/jpeg", data), data)


def test_v21_image_validation_rejects_oversized_upload():
    data = b"\xff\xd8\xff" + b"x" * (8 * 1024 * 1024)
    with pytest.raises(ValueError, match="8 Mo"):
        _validate_image_upload(_file("animation.jpg", "image/jpeg", data), data)


from app.services.audit import get_audit_tenant_id


def test_v21_audit_tenant_id_defaults_to_current_single_tenant(monkeypatch):
    monkeypatch.delenv("AUDIT_TENANT_ID", raising=False)
    assert get_audit_tenant_id() == 116


def test_v21_audit_tenant_id_rejects_invalid_values(monkeypatch):
    monkeypatch.setenv("AUDIT_TENANT_ID", "not-a-number")
    assert get_audit_tenant_id() == 116
    monkeypatch.setenv("AUDIT_TENANT_ID", "0")
    assert get_audit_tenant_id() == 116


def test_v21_audit_tenant_id_accepts_positive_value(monkeypatch):
    monkeypatch.setenv("AUDIT_TENANT_ID", "42")
    assert get_audit_tenant_id() == 42
