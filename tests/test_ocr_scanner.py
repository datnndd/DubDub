import os
import tempfile

import numpy as np

from videotrans.ocr._checkpoint import SCHEMA_VERSION
from videotrans.ocr._scanner import (
    OcrScanner,
    change_metric,
    crop_roi,
    gray_thumbnail,
)
from videotrans.ocr._types import OcrConfig, OcrResult


def _make_frame(height, width, roi_gray, h=360, w=640):
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    y0 = int(0.85 * h)
    frame[y0:, :] = roi_gray
    return frame


def _frame_stream(subtitles, fps=100.0, duration_ms=10000):
    """Yield (ts_ms, frame) every frame_ms based on subtitle intervals.

    subtitles: list of (start_ms, end_ms, text, gray_value)
    """
    interval = 1000.0 / fps
    frames = []
    ts = 0
    while ts <= duration_ms:
        active = [s for s in subtitles if s[0] <= ts < s[1]]
        gray = active[0][3] if active else 50
        frames.append((int(ts), _make_frame(360, 640, gray)))
        ts += interval
    return frames


class FakeProvider:
    def __init__(self, gray_to_text):
        self.gray_to_text = gray_to_text
        self.calls = 0

    def recognize(self, crop, language=None):
        self.calls += 1
        if crop is None:
            return OcrResult(text="", confidence=0.0)
        v = int(round(float(np.mean(crop))))
        text = self.gray_to_text.get(v, "")
        return OcrResult(text=text, confidence=0.95 if text else 0.0)


def _config(**kw):
    defaults = dict(coarse_interval_ms=500, boundary_interval_ms=150,
                    similarity_threshold=0.85, min_stable_samples=2,
                    grace_gap_ms=400, provider="paddle")
    defaults.update(kw)
    return OcrConfig(**defaults)


def test_crop_roi_and_thumbnail():
    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    frame[85:, :] = 255
    crop = crop_roi(frame, (0.0, 0.85, 1.0, 0.15))
    assert crop.shape == (15, 200, 3)
    thumb = gray_thumbnail(crop)
    assert thumb.shape == (8, 24)
    assert 0.0 <= thumb.max() <= 1.0
    assert change_metric(thumb, thumb) == 0.0


def test_scanner_produces_segments_within_tolerance():
    subs = [
        (1000, 3000, "Xin chao", 150),
        (3000, 5500, "Chaomung ban", 200),
    ]
    provider = FakeProvider({150: "Xin chao", 200: "Chaomung ban"})
    scanner = OcrScanner(provider, _config())
    segs = scanner.scan(_frame_stream(subs), duration_ms=10000)
    by_text = {s.text: s for s in segs}
    assert set(by_text) == {"Xin chao", "Chaomung ban"}
    # start boundaries within 250ms tolerance
    assert abs(by_text["Xin chao"].start_ms - 1000) <= 250
    assert abs(by_text["Chaomung ban"].start_ms - 3000) <= 250
    assert abs(by_text["Chaomung ban"].end_ms - 5500) <= 250


def test_scanner_resume_matches_uninterrupted(tmp_path):
    subs = [
        (1000, 3000, "Xin chao", 150),
        (3000, 5500, "Chaomung ban", 200),
    ]
    ckpt = tmp_path / "ckpt.json"
    provider = FakeProvider({150: "Xin chao", 200: "Chaomung ban"})

    # First scan covers only the prefix (0..3200ms) and persists a checkpoint.
    prefix = [(ts, fr) for ts, fr in _frame_stream(subs) if ts <= 3200]
    s1 = OcrScanner(provider, _config(), checkpoint_path=str(ckpt))
    s1.scan(prefix, duration_ms=10000)

    # Resume scans the full video and should dedup the resumed boundary.
    s2 = OcrScanner(provider, _config(), checkpoint_path=str(ckpt))
    resumed = s2.scan(_frame_stream(subs), duration_ms=10000, resume=True)

    # Uninterrupted reference run.
    s3 = OcrScanner(provider, _config())
    full = s3.scan(_frame_stream(subs), duration_ms=10000)

    by_text = {s.text: s for s in resumed}
    assert set(by_text) == {"Xin chao", "Chaomung ban"}
    assert sorted(s.text for s in resumed) == sorted(s.text for s in full)
    for seg in resumed:
        ref = [x for x in full if x.text == seg.text]
        assert ref, seg.text
        assert abs(seg.start_ms - ref[0].start_ms) <= 250
        assert abs(seg.end_ms - ref[0].end_ms) <= 250
def test_scanner_empty_result_returns_no_segments():
    provider = FakeProvider({})
    scanner = OcrScanner(provider, _config())
    segs = scanner.scan(_frame_stream([]), duration_ms=5000)
    assert segs == []
