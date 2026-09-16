"""Hard-Subtitle OCR Source package.

Mirrors the small-scale structure of videotrans/recognition/__init__.py: a
provider-id constant, a lazy provider registry keyed by id, and a `run` entry
that resolves the provider on demand via `get_class`.

This module is import-side-effect free and must NOT eagerly import any heavy
dependency (paddleocr, cv2, numpy, torch, PySide6) or the paddle provider
module. The paddle provider (imp="._paddle") is registered but only imported
lazily inside `run`.
"""
from typing import Optional

from videotrans import ChannelProvider, get_class

# Public re-exports.
from videotrans.ocr._types import OcrConfig, OcrResult, OcrSegment, OcrLine
from videotrans.ocr._segment import SegmentBuilder
from videotrans.ocr._text import (
    normalize_text,
    text_similarity,
    order_lines,
    representative_text,
)
from videotrans.ocr._srt_adapter import segments_to_srt_items
from videotrans.ocr._scanner import (
    crop_roi,
    gray_thumbnail,
    change_metric,
    OcrScanner,
)
from videotrans.ocr._checkpoint import (
    OcrCheckpoint,
    SCHEMA_VERSION,
    video_fingerprint,
    save_checkpoint,
    load_checkpoint,
    is_compatible,
    dedup_on_resume,
)

# Provider-id constants.
PADDLE_OCR = 0

# Lazy provider registry. The paddle provider module is added in a later task;
# reference imp="._paddle" WITHOUT importing it here.
_ID_NAME_DICT = {
    PADDLE_OCR: ChannelProvider("PaddleOCR", imp="._paddle"),
}

OCR_NAME_LIST = [it.name for it in _ID_NAME_DICT.values()]

__all__ = [
    "PADDLE_OCR",
    "OcrConfig",
    "OcrResult",
    "OcrSegment",
    "OcrLine",
    "SegmentBuilder",
    "normalize_text",
    "text_similarity",
    "order_lines",
    "representative_text",
    "segments_to_srt_items",
    "OcrCheckpoint",
    "SCHEMA_VERSION",
    "video_fingerprint",
    "save_checkpoint",
    "load_checkpoint",
    "is_compatible",
    "dedup_on_resume",
    "crop_roi",
    "gray_thumbnail",
    "change_metric",
    "OcrScanner",
    "get_provider",
    "scan_video_to_srt",
    "run",
]


def get_provider(*, provider=PADDLE_OCR, device="auto", **kwargs):
    """Build a concrete OCR provider instance (lazy import)."""
    _cls = get_class(provider, "ocr", _ID_NAME_DICT)
    if not _cls:
        raise RuntimeError(f"No this OCR Channel:{provider=}")
    return _cls(device=device, **kwargs)


def scan_video_to_srt(
    video,
    *,
    roi,
    language=None,
    device="auto",
    ffmpeg="ffmpeg",
    checkpoint_path=None,
    on_progress=None,
    provider_obj=None,
    frames=None,
    duration_ms=None,
    coarse_interval_ms=500,
):
    """Scan a video ROI with OCR and convert segments to SRT contract items.

    Returns (srt_items, segments). ``frames`` may be injected (tests); when
    omitted it streams from ``video`` via ffmpeg. ``provider_obj`` may be
    injected (tests); when omitted a Paddle provider is built lazily.
    """
    cfg = OcrConfig(
        provider="paddle",
        roi=(target_roi := tuple(roi)),
        language=language,
        device=device,
        coarse_interval_ms=coarse_interval_ms,
    )
    if not cfg.is_valid_roi():
        raise ValueError(f"Invalid OCR ROI for scan: {cfg.roi}")

    if duration_ms is None and frames is None:
        from videotrans.ocr._frame_source import probe_duration
        duration_ms = probe_duration(ffmpeg, video)

    if frames is None:
        from videotrans.ocr._frame_source import sampled_frame_iter
        frames = sampled_frame_iter(
            ffmpeg, video,
            coarse_interval_ms=coarse_interval_ms,
            duration_ms=duration_ms or 0,
        )

    if provider_obj is None:
        provider_obj = get_provider(provider=PADDLE_OCR, device=device)

    from videotrans.ocr._checkpoint import video_fingerprint
    cfg.fingerprint = video_fingerprint(video, duration_ms)

    scanner = OcrScanner(
        provider_obj, cfg,
        checkpoint_path=checkpoint_path,
        on_progress=on_progress,
    )
    segments = scanner.scan(
        frames,
        duration_ms=duration_ms or 0,
        resume=checkpoint_path is not None,
    )
    from videotrans.ocr._srt_adapter import segments_to_srt_items
    return segments_to_srt_items(segments), segments

def run(*, provider=PADDLE_OCR, image=None, language=None, **kwargs) -> OcrResult:
    """Unified OCR entry point.

    Lazily resolves the provider via ``get_class`` and calls its
    ``recognize(image, language)``. No provider module is imported at package
    import time, so importing ``videotrans.ocr`` never triggers importing the
    paddle backend.
    """
    _cls = get_class(provider, "ocr", _ID_NAME_DICT)
    if not _cls:
        raise RuntimeError(f"No this OCR Channel:{provider=}")
    return _cls(**kwargs).recognize(image, language)
