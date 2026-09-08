"""Versioned, atomic OCR scan checkpoint: fingerprint, save/load, compatibility.

Pure stdlib (dataclasses, hashlib, json, os, tempfile). No heavy imports.
"""
import hashlib
import json
import math
import os
import tempfile
from dataclasses import dataclass, field, asdict
from typing import List, Optional

from ._text import text_similarity

# Bump when the on-disk checkpoint layout changes incompatibly.
SCHEMA_VERSION = 2

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
    if not _valid_checkpoint_data(data):
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


def _valid_checkpoint_data(data):
    """Reject malformed persisted state before the scanner mutates its builder."""
    def integer(value, minimum=0):
        return type(value) is int and value >= minimum

    def number(value):
        return type(value) in (int, float) and math.isfinite(value)

    def confidence(value):
        return number(value) and 0 <= value <= 1

    try:
        if not isinstance(data, dict) or data['schema_version'] != SCHEMA_VERSION:
            return False
        if not all(isinstance(data[key], dict) for key in ('fingerprint', 'scanner_params', 'stats')):
            return False
        if not integer(data['last_processed_ms'], -1) or not isinstance(data['segments'], list):
            return False
        for segment in data['segments']:
            if not (integer(segment['start_ms']) and integer(segment['end_ms'])
                    and segment['start_ms'] <= segment['end_ms'] <= data['last_processed_ms']
                    and isinstance(segment['text'], str) and confidence(segment['confidence'])
                    and integer(segment['samples'])):
                return False
        state = data['open_candidate']
        if state is None:
            return True
        stats = data['stats']
        if not all(integer(stats[key]) for key in ('frames', 'ocr_calls')):
            return False
        if not integer(stats.get('skipped_frames', 0)):
            return False
        if not (isinstance(state['text'], str) and confidence(state['confidence'])
                and integer(state['steps'])):
            return False
        if state['last_ocr_ms'] is not None and not integer(state['last_ocr_ms']):
            return False
        thumb = state['thumbnail']
        if thumb is not None and not (isinstance(thumb, list) and len(thumb) == 8
                and all(isinstance(row, list) and len(row) == 24
                        and all(number(x) and 0 <= x <= 1 for x in row) for row in thumb)):
            return False
        builder = state['builder']
        if set(builder) != {'_state', '_cand', '_open', '_gap_start_ms', '_last_active_ts'}:
            return False
        if builder['_state'] not in ('EMPTY', 'ACTIVE') or not isinstance(builder['_cand'], list):
            return False
        for key in ('_gap_start_ms', '_last_active_ts'):
            if builder[key] is not None and not integer(builder[key]):
                return False
        for observation in builder['_cand']:
            if not (integer(observation['ts']) and isinstance(observation['text'], str)
                    and confidence(observation['confidence'])):
                return False
        opened = builder['_open']
        if (opened is not None) != (builder['_state'] == 'ACTIVE'):
            return False
        if opened is not None:
            if not (integer(opened['start_ms']) and integer(opened['last_ts'])
                    and opened['start_ms'] <= opened['last_ts'] <= data['last_processed_ms']
                    and builder['_last_active_ts'] == opened['last_ts']
                    and isinstance(opened['observations'], list) and opened['observations']):
                return False
            for text, score in opened['observations']:
                if not isinstance(text, str) or not confidence(score):
                    return False
        return True
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


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
    # Every recorded video-identity field must match before resuming.
    for key in ("path", "size", "mtime", "duration_ms", "content_hash"):
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
