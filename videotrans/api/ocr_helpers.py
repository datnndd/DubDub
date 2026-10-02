# -*- coding: utf-8 -*-
"""OCR ROI normalization and segment text extraction helpers for WebUI."""

from __future__ import annotations

import math
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
    """Extract video frames within [start_sec, end_sec), crop ROI, and run PaddleOCR."""
    try:
        from videotrans.configure.config import FFMPEG_BIN
        ffmpeg_exe = FFMPEG_BIN or getattr(runtime_config, "FFMPEG_BIN", None) or runtime_config.settings.get("ffmpeg_cmd") or "ffmpeg"
    except ImportError:
        ffmpeg_exe = getattr(runtime_config, "FFMPEG_BIN", None) or runtime_config.settings.get("ffmpeg_cmd") or "ffmpeg"
    from videotrans.ocr import PADDLE_OCR, crop_roi, get_provider
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
    start_ms = math.ceil(max(0.0, start_sec) * 1000)
    end_ms = math.ceil(max(start_sec, end_sec) * 1000)
    if start_ms >= end_ms:
        raise ValueError("OCR segment has no sampleable time inside its interval")
    last_ms = max(start_ms, end_ms - 1)

    mid_ms = (start_ms + end_ms) // 2
    step = 250 if (end_ms - start_ms) <= 6000 else 400
    sample_times = sorted(set([start_ms, min(mid_ms, last_ms), max(start_ms, end_ms - 100)]))
    if end_ms - start_ms >= 500:
        sample_times = sorted(set(list(range(start_ms, end_ms, step)) + [last_ms]))

    from videotrans.ocr._segment import SegmentBuilder
    from videotrans.ocr._types import OcrConfig, OcrResult
    from videotrans.util._srt_parse import ms_to_time_string

    builder = SegmentBuilder(
        OcrConfig(
            min_stable_samples=1,
            similarity_threshold=0.95,
            grace_gap_ms=350,
            coarse_interval_ms=step,
        )
    )

    observations = []
    decoded_frames = 0
    successful_ocr_calls = 0
    first_ocr_error: Exception | None = None
    provider = None
    for ts in sample_times:
        frame, w, h = None, 0, 0
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
            frame, w, h = frame_at(ffmpeg_exe, str(media_path), ts, end_ms=end_ms)
        if frame is None or w <= 0 or h <= 0:
            continue
        decoded_frames += 1
        try:
            cropped = crop_roi(frame, roi_tuple)
        except Exception as exc:
            raise RuntimeError(f"Could not crop the selected video region: {exc}") from exc
        if cropped is None:
            if ocr_runner is not None and (hasattr(frame, "shape") or hasattr(frame, "size")):
                cropped = frame
            else:
                raise RuntimeError("The selected OCR region contains no video pixels")
        try:
            if ocr_runner is not None:
                ocr_res = ocr_runner(cropped)
            else:
                if provider is None:
                    provider = get_provider(provider=PADDLE_OCR)
                ocr_res = provider.recognize(cropped, language)
            successful_ocr_calls += 1

            frame_text = ""
            frame_conf = 0.0
            if ocr_res:
                if isinstance(ocr_res, list):
                    observations.extend(ocr_res)
                    texts = [str(x.get("text") if isinstance(x, dict) else getattr(x, "text", x) or "").strip() for x in ocr_res]
                    texts = [t for t in texts if t]
                    frame_text = " ".join(texts)
                    confs = [float(x.get("confidence") if isinstance(x, dict) else getattr(x, "confidence", 0.0) or 0.0) for x in ocr_res]
                    frame_conf = sum(confs) / len(confs) if confs else 0.0
                elif isinstance(ocr_res, dict):
                    observations.append(ocr_res)
                    frame_text = str(ocr_res.get("text") or "").strip()
                    frame_conf = float(ocr_res.get("confidence") or 0.0)
                elif getattr(ocr_res, "text", None):
                    observations.append(ocr_res)
                    frame_text = str(getattr(ocr_res, "text", "") or "").strip()
                    frame_conf = float(getattr(ocr_res, "confidence", 0.0) or 0.0)

            builder.observe(ts, OcrResult(text=frame_text, confidence=frame_conf))
        except Exception as exc:
            if first_ocr_error is None:
                first_ocr_error = exc
            runtime_config.logger.debug(f"OCR frame error at {ts}ms: {exc}")

    if decoded_frames == 0:
        raise RuntimeError("No video frames could be decoded for this segment")
    if successful_ocr_calls == 0:
        raise RuntimeError(f"OCR could not process any sampled frame: {first_ocr_error}") from first_ocr_error

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

    raw_segments = builder.finalize()
    entries: list[dict[str, Any]] = []

    if raw_segments:
        for i, seg in enumerate(raw_segments):
            seg_text = str(seg.text or "").strip()
            if not seg_text:
                continue
            s_ms = max(start_ms, int(seg.start_ms))
            e_ms = min(end_ms, int(seg.end_ms))
            if i == len(raw_segments) - 1:
                e_ms = end_ms
            if i == 0 and s_ms - start_ms <= 500:
                s_ms = start_ms
            if e_ms <= s_ms:
                e_ms = end_ms

            entries.append({
                "startSec": round(s_ms / 1000.0, 3),
                "endSec": round(e_ms / 1000.0, 3),
                "startTime": ms_to_time_string(ms=s_ms),
                "endTime": ms_to_time_string(ms=e_ms),
                "text": seg_text,
                "confidence": round(float(seg.confidence or avg_conf or 0.0), 2),
            })
    elif normalized_obs and text:
        entries.append({
            "startSec": round(start_sec, 3),
            "endSec": round(end_sec, 3),
            "startTime": ms_to_time_string(ms=start_ms),
            "endTime": ms_to_time_string(ms=end_ms),
            "text": text,
            "confidence": round(avg_conf, 2),
        })

    return {
        "ok": True,
        "text": text,
        "confidence": round(avg_conf, 2),
        "startSec": start_sec,
        "endSec": end_sec,
        "samples": len(observations),
        "entries": entries,
    }
