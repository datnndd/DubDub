"""Versioned, atomic OCR scan checkpoint: fingerprint, save/load, compatibility.

Pure stdlib (dataclasses, hashlib, json, os, tempfile). No heavy imports.
"""
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field, asdict
from typing import List, Optional

from videotrans.ocr._text import text_similarity

# Bump when the on-disk checkpoint layout changes incompatibly.
SCHEMA_VERSION = 1

# ~1MB partial-hash window from the head and tail of the file.
_HASH_WINDOW = 1024 * 1024


def video_fingerprint(path: str, duration_ms: int = None) -> dict:
    """Build a lightweight, mostly-unique fingerprint of a video file.

    Includes normalized path, size, mtime, duration_ms, and a partial content
    hash (sha256 over the first + last ~1MB). Never reads the whole file.
    Tolerates small or missing files.
    """
    norm_path = os.path.normpath(path) if path else path
    size = None
    mtime = None
    content_hash = None

    try:
        st = os.stat(path)
        size = st.st_size
        mtime = int(st.st_mtime)
    except (OSError, TypeError):
        # Missing/unreadable file: fingerprint carries what we can.
        size = None
        mtime = None

    if size is not None:
        try:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                head = f.read(_HASH_WINDOW)
                h.update(head)
                if size > _HASH_WINDOW:
                    # Read the trailing window; overlap for tiny files is fine
                    # because we already guarded size > window.
                    tail_start = max(size - _HASH_WINDOW, 0)
                    f.seek(tail_start)
                    h.update(f.read(_HASH_WINDOW))
            content_hash = h.hexdigest()
        except OSError:
            content_hash = None

    return {
        "path": norm_path,
        "size": size,
        "mtime": mtime,
        "duration_ms": duration_ms,
        "content_hash": content_hash,
    }


@dataclass
class OcrCheckpoint:
    """Resumable, versioned OCR scan state."""

    fingerprint: dict = field(default_factory=dict)
    roi: tuple = None
    language: Optional[str] = None
    provider: Optional[str] = None
    model_version: Optional[str] = None
    device: Optional[str] = None
    scanner_params: dict = field(default_factory=dict)
    last_processed_ms: int = 0
    segments: list = field(default_factory=list)  # list of OcrSegment-as-dict
    open_candidate: Optional[dict] = None
    stats: dict = field(default_factory=dict)
    last_error: Optional[str] = None
    schema_version: int = SCHEMA_VERSION


def _segment_to_dict(seg):
    if isinstance(seg, dict):
        return dict(seg)
    # OcrSegment or similar
    keys = ("start_ms", "end_ms", "text", "confidence", "samples")
    return {k: seg[k] for k in keys}


def _checkpoint_to_jsonable(cp: OcrCheckpoint) -> dict:
    data = asdict(cp)
    # roi tuples -> lists for JSON; segments already plain via asdict if dicts,
    # but normalize any OcrSegment-like entries defensively.
    data["segments"] = [_segment_to_dict(s) for s in cp.segments]
    if cp.roi is not None:
        data["roi"] = list(cp.roi)
    return data


def save_checkpoint(cp: OcrCheckpoint, path: str):
    """Atomically write the checkpoint as JSON.

    Writes to a temp file in the same directory then os.replace onto path so a
    partial write can never corrupt an existing checkpoint.
    """
    data = _checkpoint_to_jsonable(cp)
    dir_name = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".ocr_ckpt_", suffix=".tmp", dir=dir_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        # Clean up the temp file on any failure.
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


def load_checkpoint(path: str):
    """Load a checkpoint from JSON, or return None if missing/unreadable."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    roi = data.get("roi")
    if isinstance(roi, list):
        roi = tuple(roi)
    return OcrCheckpoint(
        fingerprint=data.get("fingerprint", {}) or {},
        roi=roi,
        language=data.get("language"),
        provider=data.get("provider"),
        model_version=data.get("model_version"),
        device=data.get("device"),
        scanner_params=data.get("scanner_params", {}) or {},
        last_processed_ms=data.get("last_processed_ms", 0) or 0,
        segments=data.get("segments", []) or [],
        open_candidate=data.get("open_candidate"),
        stats=data.get("stats", {}) or {},
        last_error=data.get("last_error"),
        schema_version=data.get("schema_version", 0),
    )


def _roi_equal(a, b) -> bool:
    if a is None or b is None:
        return a == b
    try:
        if len(a) != len(b):
            return False
    except TypeError:
        return False
    return all(_num_close(x, y) for x, y in zip(a, b))


def _num_close(x, y, tol=1e-9) -> bool:
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return abs(float(x) - float(y)) <= tol
    return x == y


def is_compatible(cp, *, fingerprint, roi, language, provider, model_version, scanner_params) -> bool:
    """Return True only when the checkpoint may be auto-resumed.

    Requires schema_version match and compatible fingerprint, ROI, language,
    provider, model_version, and scanner_params. Any mismatch => False so the
    caller must NOT auto-resume an incompatible checkpoint.
    """
    if cp is None:
        return False
    if cp.schema_version != SCHEMA_VERSION:
        return False
    if not _fingerprint_compatible(cp.fingerprint, fingerprint):
        return False
    if not _roi_equal(cp.roi, roi):
        return False
    if cp.language != language:
        return False
    if cp.provider != provider:
        return False
    if cp.model_version != model_version:
        return False
    if (cp.scanner_params or {}) != (scanner_params or {}):
        return False
    return True


def _fingerprint_compatible(a: dict, b: dict) -> bool:
    a = a or {}
    b = b or {}
    # Identity-defining fields must match. duration_ms is informational and not
    # required for compatibility, but size/content_hash/path are.
    for key in ("path", "size", "content_hash"):
        if a.get(key) != b.get(key):
            return False
    return True


def _seg_range(seg):
    start = seg["start_ms"] if not hasattr(seg, "get") else seg.get("start_ms")
    end = seg["end_ms"] if not hasattr(seg, "get") else seg.get("end_ms")
    return int(start), int(end)


def _seg_text(seg):
    if hasattr(seg, "get"):
        return seg.get("text", "") or ""
    return seg["text"] or ""


def _overlaps(a_start, a_end, b_start, b_end, window_ms) -> bool:
    # Treat as overlapping if the ranges intersect within a tolerance window.
    return a_start <= b_end + window_ms and b_start <= a_end + window_ms


def dedup_on_resume(existing_segments: list, new_segments: list, *, time_window_ms: int = 300, similarity_threshold: float = 0.85) -> list:
    """Merge existing + new segments, dropping duplicate boundary overlaps.

    A new segment is dropped when its time range overlaps (within
    time_window_ms) an existing segment AND its text is similar (>= threshold).
    Distinct segments at the boundary are preserved. Result is sorted by
    start_ms.
    """
    merged = list(existing_segments or [])
    for new in (new_segments or []):
        ns, ne = _seg_range(new)
        ntext = _seg_text(new)
        replaced = False
        for i, old in enumerate(merged):
            os_, oe = _seg_range(old)
            if _overlaps(ns, ne, os_, oe, time_window_ms) and text_similarity(ntext, _seg_text(old)) >= similarity_threshold:
                if (ne - ns) > (oe - os_):
                    merged[i] = new
                replaced = True
                break
        if not replaced:
            merged.append(new)
    return sorted(merged, key=lambda s: _seg_range(s)[0])
