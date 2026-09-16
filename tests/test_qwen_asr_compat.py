import sys
from types import SimpleNamespace


def test_qwen_asr_loader_imports_pvt_model(monkeypatch):
    from videotrans.process import stt_qwen

    fake_model = type("Qwen3ASRModel", (), {})
    monkeypatch.setitem(sys.modules, "qwen_asr", SimpleNamespace(Qwen3ASRModel=fake_model))

    assert stt_qwen._load_qwen3_asr_model() is fake_model
