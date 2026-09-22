# -*- coding: utf-8 -*-
"""OCR ROI normalization and segment text extraction helpers for WebUI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from videotrans.configure import config as runtime_config


class NormalizedRoi(tuple):
    """Normalized 4-tuple (x, y, width, height) supporting dict-like key access."""

    def __new__(cls, x: float, y: float, width: float, height: float):
        return super().__new__(cls, (float(x), float(y), float(width), float(height)))

    def __getitem__(self, item: Any) -> Any:
        if isinstance(item, str):
            mapping = {"x": 0, "y": 1, "width": 2, "w": 2, "height": 3, "h": 3}
            if item in mapping:
                return super().__getitem__(mapping[item])
            raise KeyError(f"Invalid ROI key: {item}")
        return super().__getitem__(item)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except (KeyError, IndexError):
            return default


def extract_ocr_segment_text(
    media_path: Path | str,
    start_sec: float,
    end_sec: float,
    roi: Any,
    language: str | None = None,
    *,
    frame_fetcher: Any = None,
    ocr_runner: Any = None,
) -> dict[str, Any]:
    """Extract video frames across [start_sec, end_sec], crop ROI, and run PaddleOCR."""
    try:
        from videotrans.configure.config import FFMPEG_BIN
        ffmpeg_exe = FFMPEG_BIN or getattr(runtime_config, "FFMPEG_BIN", None) or runtime_config.settings.get("ffmpeg_cmd") or "ffmpeg"
    except ImportError:
        ffmpeg_exe = getattr(runtime_config, "FFMPEG_BIN", None) or runtime_config.settings.get("ffmpeg_cmd") or "ffmpeg"
    from videotrans.ocr import PADDLE_OCR, crop_roi, run as run_ocr
    from videotrans.ocr._frame_source import frame_at
    from videotrans.ocr._text import representative_text

    if isinstance(roi, dict):
        roi_tuple = (
            float(roi.get("x", 0.0)),
            float(roi.get("y", 0.0)),
            float(roi.get("width", roi.get("w", 1.0))),
            float(roi.get("height", roi.get("h", 1.0))),
        )
    elif isinstance(roi, (list, tuple)) and len(roi) == 4:
        roi_tuple = (float(roi[0]), float(roi[1]), float(roi[2]), float(roi[3]))
    else:
        roi_tuple = (0.0, 0.0, 1.0, 1.0)

    ffmpeg_exe = ffmpeg_exe or "ffmpeg"
    start_ms = int(max(0.0, start_sec) * 1000)
    end_ms = int(max(start_sec, end_sec) * 1000)

    mid_ms = (start_ms + end_ms) // 2
    sample_times = sorted(set([start_ms, mid_ms, max(start_ms, end_ms - 100)]))
    if end_ms - start_ms >= 1000:
        sample_times = sorted(set(list(range(start_ms, end_ms, 500)) + [end_ms]))

    observations = []
    for ts in sample_times:
        if frame_fetcher is not None:
            try:
                res = frame_fetcher(media_path, ts / 1000.0)
            except TypeError:
                res = frame_fetcher(ffmpeg_exe, str(media_path), ts)
            if isinstance(res, tuple):
                frame, w, h = res[:3]
            elif res is not None:
                frame = res
                if hasattr(frame, "shape") and len(frame.shape) >= 2:
                    h, w = frame.shape[:2]
                elif hasattr(frame, "size") and isinstance(frame.size, tuple) and len(frame.size) >= 2:
                    w, h = frame.size[:2]
                else:
                    w, h = 0, 0
        else:
            frame, w, h = frame_at(ffmpeg_exe, str(media_path), ts)
        if frame is None or w <= 0 or h <= 0:
            continue
        try:
            cropped = crop_roi(frame, roi_tuple)
        except Exception:
            cropped = None
        if cropped is None:
            if ocr_runner is not None and (hasattr(frame, "shape") or hasattr(frame, "size")):
                cropped = frame
            else:
                continue
        try:
            if ocr_runner is not None:
                ocr_res = ocr_runner(cropped)
            else:
                ocr_res = run_ocr(provider=PADDLE_OCR, image=cropped, language=language)
            if ocr_res:
                if isinstance(ocr_res, list):
                    observations.extend(ocr_res)
                elif getattr(ocr_res, "text", None):
                    observations.append(ocr_res)
        except Exception as exc:
            runtime_config.logger.debug(f"OCR frame error at {ts}ms: {exc}")

    normalized_obs: list[tuple[str, float]] = []
    for obs in observations:
        if isinstance(obs, dict):
            t = str(obs.get("text") or "").strip()
            c = float(obs.get("confidence") or 0.0)
        elif hasattr(obs, "text") and hasattr(obs, "confidence"):
            t = str(getattr(obs, "text", "") or "").strip()
            c = float(getattr(obs, "confidence", 0.0) or 0.0)
        elif isinstance(obs, (list, tuple)):
            t = str(obs[0] or "").strip()
            c = float(obs[1]) if len(obs) > 1 and obs[1] is not None else 0.0
        else:
            t = str(obs).strip()
            c = 0.0
        if t:
            normalized_obs.append((t, c))

    if normalized_obs:
        text = representative_text(normalized_obs)
        avg_conf = sum(c for _, c in normalized_obs) / len(normalized_obs)
    else:
        text = ""
        avg_conf = 0.0

    return {
        "ok": True,
        "text": text,
        "confidence": round(avg_conf, 2),
        "startSec": start_sec,
        "endSec": end_sec,
        "samples": len(observations),
    }
