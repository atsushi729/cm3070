"""Helpers for streaming uploaded files into application-managed storage."""
from __future__ import annotations

import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import BinaryIO


def store_upload(
    source: BinaryIO,
    storage_dir: Path,
    original_filename: str | None,
    *,
    default_filename: str,
) -> tuple[Path, str]:
    """Persist an upload under a timestamped unique name; return its path and
    user-facing filename."""
    filename = original_filename or default_filename
    suffix = Path(filename).suffix or Path(default_filename).suffix
    stored_name = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}{suffix}"
    destination = storage_dir / stored_name
    with destination.open("wb") as output:
        shutil.copyfileobj(source, output)
    return destination, original_filename or stored_name
