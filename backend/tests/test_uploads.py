from __future__ import annotations

import io

from app.services.uploads import store_upload


def test_store_upload_preserves_extension_and_content(tmp_path):
    destination, filename = store_upload(
        io.BytesIO(b"payload"), tmp_path, "call.mp3", default_filename="call.wav"
    )

    assert destination.parent == tmp_path
    assert destination.suffix == ".mp3"
    assert destination.read_bytes() == b"payload"
    assert filename == "call.mp3"


def test_store_upload_uses_generated_name_when_original_is_missing(tmp_path):
    destination, filename = store_upload(
        io.BytesIO(b"image"), tmp_path, None, default_filename="photo.jpg"
    )

    assert destination.suffix == ".jpg"
    assert filename == destination.name
