# -*- coding: utf-8 -*-
"""Content hashing and deduplication utilities for media files."""
from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK_SIZE = 256 * 1024


def compute_content_hash(path: str | Path) -> str:
    """Compute SHA-256 hash of a media or audio file in 256KB chunks."""
    p = Path(path)
    if not p.is_file():
        return ""
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            chunk = f.read(_CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
