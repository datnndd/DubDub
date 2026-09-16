"""Streamed, memory-bounded OCR scanner with checkpoint/resume.

The scanner decodes a video sequentially (via an injected frame iterator),
crops only the ROI in memory, samples coarsely, uses a cheap grayscale change
metric to run OCR selectively, refines transitions locally, and feeds a
SegmentBuilder. It persists an atomic checkpoint after each closed segment and
periodically, and can resume from a compatible checkpoint with a short overlap.

This module uses only Python stdlib + numpy. It never imports PaddleOCR, cv2,
or torch. A frame iterator yields ``(timestamp_ms, frame_bgr)`` tuples; the
production producer lives in ``_frame_source`` and tests inject small lists.
"""
from typing import Callable, Iterable, List, Optional, Tuple

import numpy as np

from videotrans.ocr._checkpoint import (
    OcrCheckpoint,
    dedup_on_resume,
    is_compatible,
    load_checkpoint,
    save_checkpoint,
)
from videotrans.ocr._segment import SegmentBuilder
from videotrans.ocr._types import OcrConfig, OcrResult, OcrSegment

# Default fallback when config does not provide a checkpoint interval.
_CHECKPOINT_INTERVAL_MS = 30_000
_FINE_STEP_MS = 150
# Frames are decoded without scaling; thumbnails are scaled by block averaging.
_GRID_W = 24
_GRID_H = 8
_DEFAULT_CHANGE_THRESHOLD = 0.02
# Re-run OCR every N coarse steps even without a detected change, and whenever
# the latest observation confidence is below this value.
_CONFIRM_EVERY = 4
_LOW_CONFIDENCE = 0.65


def gray_thumbnail(roi_bgr, grid_w: int = _GRID_W, grid_h: int = _GRID_H) -> np.ndarray:
    """Downsample a BGR crop to a small normalized grayscale thumb (0..1).

    Pure numpy; stable memory regardless of video duration because only one
    thumbnail is held at a time.
    """
    if roi_bgr is None:
        return _empty_thumb(grid_w, grid_h)
    arr = np.asarray(roi_bgr)
    if arr.ndim == 2:
        gray = arr.astype(np.float32)
    elif arr.ndim == 3:
        gray = (
            0.299 * arr[..., 2].astype(np.float32)
            + 0.587 * arr[..., 1].astype(np.float32)
            + 0.114 * arr[..., 0].astype(np.float32)
        )
    else:
        return _empty_thumb(grid_w, grid_h)
    h, w = gray.shape
    if h == 0 or w == 0:
        return _empty_thumb(grid_w, grid_h)
    # Block-averaged downsample to grid.
    if h >= grid_h and w >= grid_w:
        rows_per = h // grid_h
        cols_per = w // grid_w
        uh = rows_per * grid_h
        uw = cols_per * grid_w
        resized = (
            gray[:uh, :uw]
            .reshape(grid_h, rows_per, grid_w, cols_per)
            .mean(axis=(1, 3))
        )
    else:
        # Smaller than grid in at least one axis: nearest resize.
        resized = _resize_nearest(gray, grid_h, grid_w)
    lo, hi = float(resized.min()), float(resized.max())
    if hi - lo < 1e-6:
        return np.zeros_like(resized, dtype=np.float32)
    return ((resized.astype(np.float32) - lo) / (hi - lo)).astype(np.float32)


def _empty_thumb(grid_w, grid_h):
    return np.zeros((grid_h, grid_w), dtype=np.float32)


def _resize_nearest(gray, out_h, out_w):
    h, w = gray.shape
    ys = (np.arange(out_h) * h / out_h).astype(np.int64)
    xs = (np.arange(out_w) * w / out_w).astype(np.int64)
    return gray[np.ix_(np.clip(ys, 0, h - 1), np.clip(xs, 0, w - 1))].astype(np.float32)


def change_metric(a: np.ndarray, b: np.ndarray) -> float:
    """Mean absolute difference between two normalized thumbs (0..1)."""
    if a is None or b is None:
        return 1.0
    return float(np.mean(np.abs(a - b)))


def crop_roi(frame, roi) -> Optional[np.ndarray]:
    """Crop a normalized (x, y, w, h) ROI from a frame, returning a fresh copy."""
    if frame is None:
        return None
    arr = np.asarray(frame)
    if arr.ndim not in (2, 3):
        return None
    h, w = arr.shape[:2]
    if h <= 0 or w <= 0:
        return None
    x, y, rw, rh = roi
    x0 = int(round(x * w))
    y0 = int(round(y * h))
    x1 = min(w, int(round((x + rw) * w)))
    y1 = min(h, int(round((y + rh) * h)))
    if x1 <= x0 or y1 <= y0:
        return None
    return np.array(arr[y0:y1, x0:x1], copy=True)


class OcrScanner:
    """Stream OCR over frames, consolidate segments, persist checkpoints.

    ``frames`` is an iterable of ``(timestamp_ms, frame_bgr)``. In production a
    video frame producer supplies it; tests inject small lists.
    """

    def __init__(
        self,
        provider,
        config: OcrConfig,
        *,
        checkpoint_path: Optional[str] = None,
        on_progress: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self.provider = provider
        self.config = config
        self.checkpoint_path = checkpoint_path
        self.on_progress = on_progress
        self._builder = SegmentBuilder(config)
        self._last_thumb = None
        self._last_ocr_ts = None
        self._last_norm = ""
        self._last_conf = 0.0
        self._coarse_steps = 0
        self._last_ckpt_ms = 0
        self._stats = {"frames": 0, "ocr_calls": 0, "cpu": "cpu"}
        self._saved_last_processed_ms = 0
        self._preexisting = []

    # -- progress ---------------------------------------------------------
    def _report(self, ts_ms, duration_ms):
        if not self.on_progress:
            return
        self.on_progress(
            {
                "timestamp_ms": ts_ms,
                "duration_ms": duration_ms,
                "percent": (ts_ms / duration_ms * 100.0) if duration_ms else 0.0,
                "device": self._stats.get("cpu"),
                "segments": len(self._builder.segments) if hasattr(self._builder, "segments") else self._count_segments(),
                "latest_text": self._last_norm,
                "ocr_calls": self._stats["ocr_calls"],
            }
        )

    def _count_segments(self):
        try:
            return len(self._builder._segments)
        except Exception:
            return 0

    # -- main scan --------------------------------------------------------
    def scan(self, frames: Iterable[Tuple[int, np.ndarray]], duration_ms: int = 0, *, stop_event: Optional[Callable[[], bool]] = None, resume: bool = True) -> List:
        """Run the scan over ``frames`` and return the finalized segments."""
        roi = self.config.roi
        if not self.config.is_valid_roi():
            raise ValueError(f"Invalid ROI for OCR scan: {self.config.roi}")

        loaded_ckpt = self._maybe_load_checkpoint(resume)
        skip_until_ms = 0
        self._preexisting = []
        if loaded_ckpt is not None:
            overlap = self.config.coarse_interval_ms * 4 + 3000
            skip_until_ms = max(0, loaded_ckpt.last_processed_ms - overlap)
            self._preexisting = [self._dict_to_seg(x) for x in loaded_ckpt.segments]

        for ts_ms, frame in frames:
            ts_ms = int(ts_ms)
            if stop_event is not None and stop_event():
                break
            self._stats["frames"] += 1
            if ts_ms < skip_until_ms:
                continue
            self._process_frame(ts_ms, frame, roi, duration_ms)
            if self._coarse_steps % _CONFIRM_EVERY == 0:
                self._maybe_periodic_checkpoint(ts_ms)

        # Stop event or exhausted input: persist final checkpoint and finalize.
        return self.finalize(duration_ms, persist=True)

    # -- per-frame processing ---------------------------------------------
    def _process_frame(self, ts_ms, frame, roi, duration_ms):
        crop = crop_roi(frame, roi)
        thumb = gray_thumbnail(crop)
        if self._last_thumb is None:
            self._last_thumb = thumb
            # First frame: OCR once to seed.
            self._ocr_observe(ts_ms, frame, roi)
            self._last_thumb = thumb
            self._coarse_steps += 1
            self._report(ts_ms, duration_ms)
            return

        delta = change_metric(self._last_thumb, thumb)
        self._last_thumb = thumb
        self._coarse_steps += 1

        needs_ocr = (
            delta > getattr(self.config, "change_threshold", _DEFAULT_CHANGE_THRESHOLD)
            or self._coarse_steps % _CONFIRM_EVERY == 0
            or self._last_conf < _LOW_CONFIDENCE
        )
        if not needs_ocr:
            self._report(ts_ms, duration_ms)
            return

        new_norm_before = self._last_norm
        prev_ocr_ts = self._last_ocr_ts
        result = self._ocr(ts_ms, frame, roi)
        self._last_ocr_ts = ts_ms
        self._report(ts_ms, duration_ms)

        # Boundary refinement on a text transition without an empty gap.
        if (
            self._last_norm and new_norm_before and self._last_norm != new_norm_before
            and prev_ocr_ts is not None and (ts_ms - prev_ocr_ts) <= self.config.coarse_interval_ms + 200
        ):
            self._refine(prev_ocr_ts, ts_ms, frame, roi, duration_ms)

    def _ocr(self, ts_ms, frame, roi):
        crop = crop_roi(frame, roi)
        result = self.provider.recognize(crop, self.config.language)
        if result is None:
            result = OcrResult(timestamp_ms=ts_ms)
        result.timestamp_ms = ts_ms
        self._stats["ocr_calls"] += 1
        self._last_norm = _normalize_for_track(result.text)
        self._last_conf = float(getattr(result, "confidence", 0.0) or 0.0)
        self._builder.observe(ts_ms, result)
        return result

    def _ocr_observe(self, ts_ms, frame, roi):
        crop = crop_roi(frame, roi)
        result = self.provider.recognize(crop, self.config.language)
        if result is None:
            result = OcrResult(timestamp_ms=ts_ms)
        result.timestamp_ms = ts_ms
        self._stats["ocr_calls"] += 1
        self._last_norm = _normalize_for_track(result.text)
        self._last_conf = float(getattr(result, "confidence", 0.0) or 0.0)
        self._builder.observe(ts_ms, result)
        return result

    def _refine(self, from_ts, to_ts, frame, roi, duration_ms):
        """Scan the transition window at a finer step to fix the boundary."""
        step = _FINE_STEP_MS
        t = from_ts + step
        while t < to_ts - step:
            self._ocr(t, frame, roi)
            self._report(t, duration_ms)
            t += step

    def _maybe_periodic_checkpoint(self, ts_ms):
        if not self.checkpoint_path:
            return
        if ts_ms - self._last_ckpt_ms >= getattr(self.config, "checkpoint_interval_ms", _CHECKPOINT_INTERVAL_MS):
            self._save_checkpoint(ts_ms, last_error=None)
            self._last_ckpt_ms = ts_ms

    # -- checkpoint -------------------------------------------------------
    def _maybe_load_checkpoint(self, resume):
        if not resume or not self.checkpoint_path:
            return None
        cp = load_checkpoint(self.checkpoint_path)
        if cp is None:
            return None
        fp = self._fingerprint()
        if not is_compatible(
            cp,
            fingerprint=fp,
            roi=self.config.roi,
            language=self.config.language,
            provider=getattr(self.config, "provider", "paddle"),
            model_version=None,
            scanner_params=self._scanner_params(),
        ):
            return None
        self._saved_last_processed_ms = cp.last_processed_ms
        return cp

    def _fingerprint(self):
        # Provided by the frame producer via config extension if available.
        fp = getattr(self.config, "fingerprint", None)
        if fp:
            return fp
        return {"path": None, "size": None, "content_hash": None}

    def _scanner_params(self):
        return {
            "coarse_interval_ms": self.config.coarse_interval_ms,
            "boundary_interval_ms": self.config.boundary_interval_ms,
            "similarity_threshold": self.config.similarity_threshold,
            "min_stable_samples": self.config.min_stable_samples,
            "grace_gap_ms": self.config.grace_gap_ms,
        }

    def _save_checkpoint(self, ts_ms, last_error=None):
        if not self.checkpoint_path:
            return
        cp = OcrCheckpoint(
            fingerprint=self._fingerprint(),
            roi=tuple(self.config.roi),
            language=self.config.language,
            provider=getattr(self.config, "provider", "paddle"),
            model_version=None,
            device=self._stats.get("cpu"),
            scanner_params=self._scanner_params(),
            last_processed_ms=int(ts_ms),
            segments=[self._seg_to_dict(s) for s in self._builder.snapshot_completed()],
            open_candidate=None,
            stats=dict(self._stats),
            last_error=last_error,
        )
        save_checkpoint(cp, self.checkpoint_path)

    @staticmethod
    def _dict_to_seg(d):
        try:
            return OcrSegment(
                start_ms=int(d.get("start_ms", 0)),
                end_ms=int(d.get("end_ms", 0)),
                text=d.get("text", ""),
                confidence=float(d.get("confidence", 0.0) or 0.0),
                samples=int(d.get("samples", 0)),
            )
        except Exception:
            return OcrSegment(text="")

    @staticmethod
    def _seg_to_dict(seg):
        try:
            return {"start_ms": seg["start_ms"], "end_ms": seg["end_ms"], "text": seg["text"], "confidence": seg["confidence"], "samples": seg["samples"]}
        except Exception:
            return {"start_ms": 0, "end_ms": 0, "text": "", "confidence": 0.0, "samples": 0}

    def finalize(self, duration_ms=0, *, persist=False) -> List:
        segments = self._builder.finalize()
        if self.checkpoint_path and persist:
            last_ts = self._last_ocr_ts or 0
            self._save_checkpoint(last_ts, last_error=None)
        # De-duplicate the resumed-overlap boundary against preexisting segments.
        if self._preexisting:
            segments = dedup_on_resume(self._preexisting, segments)
        return segments


def _normalize_for_track(text: str) -> str:
    from videotrans.ocr._text import normalize_text

    return normalize_text(text)


