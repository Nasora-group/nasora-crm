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
