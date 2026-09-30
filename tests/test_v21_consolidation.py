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
