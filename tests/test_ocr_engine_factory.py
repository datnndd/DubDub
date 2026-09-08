"""Paddle major-version adapters keep installed environments usable."""
import importlib.metadata
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engines.hardsub_ocr import main
from engines.hardsub_ocr import bootstrap
from engines.hardsub_ocr.ocr import _paddle
from engines.hardsub_ocr.ocr._providers import EngineProvider
from engines.hardsub_ocr.ocr._types import OcrLine, OcrResult


def test_paddle2_uses_reference_provider_and_shared_score_filter(monkeypatch):
    monkeypatch.setattr(importlib.metadata, 'version', lambda _: '2.10.0')
    class Provider:
        def __init__(self, device): assert device == 'cpu'
        def map_language(self, language): return 'ch'
        def _require_engine(self, device): assert device == 'cpu'
        def recognize(self, image, language=None):
            return OcrResult(text='keep noise', confidence=.6, lines=[
                OcrLine('keep', .99, (0, 0, 10, 10)),
                OcrLine('noise', .1, (20, 0, 10, 10)),
            ])
    monkeypatch.setattr(_paddle, 'PaddleOcrProvider', Provider)
    result = EngineProvider(main._create_ocr_engine('paddleocr')).recognize(None)
    assert result.text == 'keep'
    assert result.confidence == .99


def test_paddle3_keeps_installed_predict_api(monkeypatch):
    monkeypatch.setattr(importlib.metadata, 'version', lambda _: '3.7.0')
    class Paddle:
        def __init__(self, **kwargs):
            assert kwargs['ocr_version'] == 'PP-OCRv5'
            assert kwargs['use_textline_orientation'] is False
        def predict(self, image):
            return [dict(rec_texts=['keep'], rec_scores=[.99], rec_polys=[])]
    monkeypatch.setitem(sys.modules, 'paddleocr', SimpleNamespace(PaddleOCR=Paddle))
    result = EngineProvider(main._create_ocr_engine('paddleocr')).recognize(None)
    assert result.text == 'keep'


def test_paddle_probe_loads_torch_before_paddle(monkeypatch):
    import builtins
    events = []
    original_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        if name in ('torch', 'paddleocr', 'paddle'):
            if name != 'torch':
                assert 'torch' in events, 'Paddle probe must match the provider DLL import ordering'
            events.append(name)
            return SimpleNamespace()
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(_paddle.PaddleOcrProvider, '_ensure_win_dlls', lambda: None)
    monkeypatch.setattr(builtins, '__import__', guarded_import)
    previous_path = list(sys.path)
    try:
        exec(bootstrap._PADDLE_IMPORT_PROBE, {})
    finally:
        sys.path[:] = previous_path
    assert events == ['torch', 'paddleocr', 'paddle']


def test_legacy_fallback_accepts_shared_provider_contract(monkeypatch, tmp_path):
    (tmp_path / 'f_000001.png').write_bytes(b'fixture')
    monkeypatch.setattr(main, '_frame_thumbnail', lambda _: __import__('numpy').ones((8, 24)))
    monkeypatch.setattr(main, '_create_ocr_engine', lambda _: lambda _image: OcrResult(
        text='first second', confidence=.9, lines=[
            OcrLine('second', .95, (0, 20, 10, 10)),
            OcrLine('first', .99, (0, 0, 10, 10)),
        ]))
    cues = main._run_ocr(str(tmp_path), .5, 1, 2, lambda event: None, 'paddleocr')
    assert cues == [dict(start=0, end=.5, text='first second')]
