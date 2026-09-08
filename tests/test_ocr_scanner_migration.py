import sys
from pathlib import Path

import numpy as np
import pytest
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engines.hardsub_ocr.ocr._scanner import OcrScanner
from engines.hardsub_ocr.ocr._types import OcrConfig, OcrResult


def test_static_subtitle_skips_inference_without_truncating_end():
    class Provider:
        calls = 0
        def recognize(self, image, language=None):
            self.calls += 1
            return OcrResult(text='visible subtitle', confidence=.99)

    provider = Provider()
    frame = np.zeros((20, 100, 3), dtype=np.uint8)
    frame[5:15, 20:80] = 255
    scanner = OcrScanner(provider, OcrConfig(roi=(0, 0, 1, 1)))
    segments = scanner.scan(((i * 500, frame) for i in range(100)), duration_ms=50000)
    assert provider.calls <= 26
    assert len(segments) == 1
    assert segments[0].text == 'visible subtitle'
    assert segments[0].end_ms == 49500


def test_resume_preserves_open_cue_and_confirmation_cadence(tmp_path):
    class Provider:
        def recognize(self, image, language=None):
            return OcrResult(text='same text', confidence=.95)

    frame = np.zeros((20, 100, 3), dtype=np.uint8)
    frame[5:15, 20:80] = 255
    frames = [(i * 500, frame) for i in range(30)]
    config = OcrConfig(roi=(0, 0, 1, 1))
    path = str(tmp_path / 'checkpoint.json')
    OcrScanner(Provider(), config, checkpoint_path=path).scan(frames[:13])
    resumed = OcrScanner(Provider(), config, checkpoint_path=path).scan(frames)
    reference = OcrScanner(Provider(), config).scan(frames)
    assert resumed == reference


def test_changed_model_or_crop_rejects_checkpoint(tmp_path):
    class Provider:
        def __init__(self, text):
            self.text = text
        def recognize(self, image, language=None):
            return OcrResult(text=self.text, confidence=.99)

    frames = [(i * 500, np.zeros((20, 100, 3), dtype=np.uint8)) for i in range(8)]
    config = OcrConfig(roi=(0, 0, 1, 1))
    config.source_crop = dict(top=.8)
    config.model_identity = 'rapidocr'
    path = str(tmp_path / 'checkpoint.json')
    OcrScanner(Provider('old'), config, checkpoint_path=path).scan(frames)
    config.model_identity = 'paddleocr'
    result = OcrScanner(Provider('new'), config, checkpoint_path=path).scan(frames)
    assert [segment.text for segment in result] == ['new']
    config.source_crop = dict(top=.7)
    result = OcrScanner(Provider('new crop'), config, checkpoint_path=path).scan(frames)
    assert [segment.text for segment in result] == ['new crop']


def test_non_object_checkpoint_is_ignored(tmp_path):
    from engines.hardsub_ocr.ocr._checkpoint import load_checkpoint
    path = tmp_path / 'checkpoint.json'
    path.write_text('[]', encoding='utf-8')
    assert load_checkpoint(str(path)) is None


def test_progress_preserves_display_text_and_accounts_for_skips():
    class Provider:
        def recognize(self, image, language=None):
            return OcrResult(text='Hello, World!', confidence=.99)

    events = []
    frame = np.zeros((20, 100, 3), dtype=np.uint8)
    scanner = OcrScanner(Provider(), OcrConfig(roi=(0, 0, 1, 1)), on_progress=events.append)
    scanner.scan(((i * 500, frame) for i in range(8)), duration_ms=4000)
    assert events[-1]['latest_text'] == 'Hello, World!'
    assert events[-1]['decoded_frames'] == 8
    assert events[-1]['ocr_calls'] == 3
    assert events[-1]['skipped_frames'] == 5
    assert events[-1]['cache_hits'] == 0


def test_refinement_uses_historical_images_in_timestamp_order():
    class Provider:
        def recognize(self, image, language=None):
            return OcrResult(text='first' if image[0, 0, 0] == 0 else 'second', confidence=.99)

    first = np.zeros((20, 100, 3), dtype=np.uint8)
    second = first.copy()
    second[:, 50:] = 255
    second[0, 0, 0] = 255
    requested = []
    config = OcrConfig(roi=(0, 0, 1, 1), boundary_interval_ms=150)
    def frame_at(ts):
        requested.append(ts)
        return first if ts < 400 else second
    config.frame_at = frame_at
    scanner = OcrScanner(Provider(), config)
    observed = []
    original_observe = scanner._builder.observe
    def observe(ts, result):
        observed.append(ts)
        original_observe(ts, result)
    scanner._builder.observe = observe
    segments = scanner.scan([(0, first), (500, second), (1000, second)])
    assert requested == [150, 300, 450]
    assert observed == sorted(observed)
    assert [(s.text, s.start_ms, s.end_ms) for s in segments] == [
        ('first', 0, 450), ('second', 450, 1000),
    ]


@pytest.mark.parametrize('field,value', [
    ('fingerprint', []), ('stats', {'frames': 'eight', 'ocr_calls': 1}),
    ('last_processed_ms', '500'), ('segments', [{'text': 'bad'}]),
    ('open_candidate', {}),
    ('open_candidate.thumbnail', [[0]]),
    ('open_candidate.confidence', float('nan')),
    ('open_candidate.builder._open.observations', [['broken']]),
    ('open_candidate.builder._state', 'ACTIVE_BROKEN'),
])
def test_malformed_checkpoint_state_restarts_cleanly(tmp_path, field, value):
    class Provider:
        def __init__(self, text): self.text = text
        def recognize(self, image, language=None):
            return OcrResult(text=self.text, confidence=.99)
    frames = [(i * 500, np.zeros((20, 100, 3), dtype=np.uint8)) for i in range(8)]
    config = OcrConfig(roi=(0, 0, 1, 1))
    path = tmp_path / 'state.json'
    OcrScanner(Provider('old'), config, checkpoint_path=str(path)).scan(frames)
    data = json.loads(path.read_text(encoding='utf-8'))
    target = data
    keys = field.split('.')
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value
    path.write_text(json.dumps(data), encoding='utf-8')
    result = OcrScanner(Provider('fresh'), config, checkpoint_path=str(path)).scan(frames)
    assert [segment.text for segment in result] == ['fresh']


def test_cancel_preserves_checkpoint_without_returning_partial_transcript(tmp_path):
    class Provider:
        def recognize(self, image, language=None):
            return OcrResult(text='subtitle', confidence=.99)
    frames = [(i * 500, np.zeros((20, 100, 3), dtype=np.uint8)) for i in range(10)]
    path = str(tmp_path / 'cancel.json')
    config = OcrConfig(roi=(0, 0, 1, 1))
    scanner = OcrScanner(Provider(), config, checkpoint_path=path)
    with pytest.raises(RuntimeError, match='cancelled'):
        scanner.scan(frames, stop_event=lambda: scanner._stats['frames'] >= 5)
    resumed = OcrScanner(Provider(), config, checkpoint_path=path).scan(frames)
    uninterrupted = OcrScanner(Provider(), config).scan(frames)
    assert resumed == uninterrupted


@pytest.mark.parametrize('before,after,expected', [
    ('', 'visible', [('', 150), ('', 300), ('visible', 450)]),
    ('visible', '', [('visible', 150), ('visible', 300), ('', 450)]),
])
def test_refines_empty_text_boundaries(before, after, expected):
    class Provider:
        def recognize(self, image, language=None):
            text = before if image[0, 0, 0] == 0 else after
            return OcrResult(text=text, confidence=.99 if text else 0)
    first = np.zeros((20, 100, 3), dtype=np.uint8)
    second = np.zeros((20, 100, 3), dtype=np.uint8)
    second[:, 40:] = 255
    second[0, 0] = 255
    config = OcrConfig(roi=(0, 0, 1, 1), boundary_interval_ms=150)
    config.frame_at = lambda ts: first if ts < 400 else second
    scanner = OcrScanner(Provider(), config)
    observations = []
    original = scanner._builder.observe
    def observe(ts, result):
        if ts not in (0, 500): observations.append((result.text, ts))
        original(ts, result)
    scanner._builder.observe = observe
    scanner.scan([(0, first), (500, second)])
    assert observations == expected
