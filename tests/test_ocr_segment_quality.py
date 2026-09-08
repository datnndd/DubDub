from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engines.hardsub_ocr.ocr._scanner import OcrScanner
from engines.hardsub_ocr.ocr._segment import SegmentBuilder
from engines.hardsub_ocr.ocr._types import OcrConfig, OcrResult


def result(text, confidence=.99):
    return OcrResult(text=text, confidence=confidence if text else 0)


def test_jitter_uses_confidence_weighted_consensus_without_fragmenting():
    builder = SegmentBuilder(OcrConfig(roi=(0, 0, 1, 1), min_stable_samples=2))
    builder.observe(0, result('Correct subtitle', .75))
    builder.observe(500, result('Correct subtitle', .85))
    builder.observe(1000, result('Correct subtit1e', .55))
    builder.observe(1500, result('Correct subtitle', .95))
    segments = builder.finalize()
    assert len(segments) == 1
    assert segments[0].text == 'Correct subtitle'
    assert segments[0].start_ms == 0
    assert segments[0].end_ms == 1500


def test_repeated_text_after_real_gap_remains_two_cues():
    builder = SegmentBuilder(OcrConfig(roi=(0, 0, 1, 1), grace_gap_ms=400))
    for timestamp, text in [(0, 'Again'), (500, ''), (1000, 'Again'), (1500, '')]:
        builder.observe(timestamp, result(text))
    segments = builder.finalize()
    assert [(item.text, item.start_ms) for item in segments] == [('Again', 0), ('Again', 1000)]


def test_adjacent_texts_split_at_transition_and_empty_roi_emits_nothing():
    builder = SegmentBuilder(OcrConfig(roi=(0, 0, 1, 1)))
    builder.observe(0, result('First'))
    builder.observe(500, result('Second'))
    segments = builder.finalize()
    assert [(item.text, item.start_ms, item.end_ms) for item in segments] == [
        ('First', 0, 500), ('Second', 500, 500),
    ]
    empty = SegmentBuilder(OcrConfig(roi=(0, 0, 1, 1)))
    for timestamp in range(0, 2000, 500):
        empty.observe(timestamp, result(''))
    assert empty.finalize() == []


def test_low_contrast_fade_is_detected_and_bridged():
    class Provider:
        def recognize(self, image, language=None):
            return result('Faded subtitle', .8) if image.max() else result('')
    blank = np.zeros((20, 100, 3), dtype=np.uint8)
    faint = blank.copy()
    faint[7:13, 15:85] = 18
    scanner = OcrScanner(Provider(), OcrConfig(roi=(0, 0, 1, 1), min_stable_samples=2))
    segments = scanner.scan([(0, blank), (500, faint), (1000, faint),
                             (1500, blank), (2000, blank)])
    assert [(item.text, item.start_ms, item.end_ms) for item in segments] == [
        ('Faded subtitle', 500, 1000),
    ]
