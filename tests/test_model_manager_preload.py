from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

import pytest


@pytest.fixture
def model_manager(monkeypatch):
    for mod_name in ("core.config", "services.model_manager"):
        if getattr(sys.modules.get(mod_name), "__file__", None) is None:
            sys.modules.pop(mod_name, None)

    import services.model_manager as mm

    monkeypatch.setattr(mm, "_torch", None)
    monkeypatch.setattr(mm, "_OmniVoice", None)
    monkeypatch.setattr(mm, "model", None)
    monkeypatch.setenv("OMNIVOICE_MODEL", "test/checkpoint")
    return mm


def test_tts_asr_preload_is_opt_in(model_manager, monkeypatch):
    monkeypatch.delenv("OMNIVOICE_PRELOAD_TTS_ASR", raising=False)
    assert model_manager.should_preload_tts_asr() is False

    for value in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("OMNIVOICE_PRELOAD_TTS_ASR", value)
        assert model_manager.should_preload_tts_asr() is True

    monkeypatch.setenv("OMNIVOICE_PRELOAD_TTS_ASR", "0")
    assert model_manager.should_preload_tts_asr() is False


def test_load_model_skips_pytorch_whisper_by_default(model_manager, monkeypatch):
    calls = []

    class DummyOmniVoice:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(llm=object())

    monkeypatch.delenv("OMNIVOICE_PRELOAD_TTS_ASR", raising=False)
    monkeypatch.setattr(model_manager, "_lazy_torch", lambda: SimpleNamespace(float16="float16"))
    monkeypatch.setattr(model_manager, "_lazy_omnivoice", lambda: DummyOmniVoice)
    monkeypatch.setattr(model_manager, "get_best_device", lambda: "mps")

    loaded = model_manager._load_model_sync()

    assert loaded.llm is not None
    assert calls == [
        (
            ("test/checkpoint",),
            {"device_map": "mps", "dtype": "float16", "load_asr": False},
        )
    ]


def test_load_model_can_preload_pytorch_whisper_when_requested(model_manager, monkeypatch):
    calls = []
    asr_loads = []

    class DummyModel:
        llm = object()

        def load_asr_model(self):
            asr_loads.append(True)

    class DummyOmniVoice:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            calls.append((args, kwargs))
            return DummyModel()

    monkeypatch.setenv("OMNIVOICE_PRELOAD_TTS_ASR", "1")
    monkeypatch.setattr(model_manager, "_lazy_torch", lambda: SimpleNamespace(float16="float16"))
    monkeypatch.setattr(model_manager, "_lazy_omnivoice", lambda: DummyOmniVoice)
    monkeypatch.setattr(model_manager, "get_best_device", lambda: "mps")

    model_manager._load_model_sync()

    assert calls[0][1]["load_asr"] is False
    assert asr_loads == [True]


def test_resolve_checkpoint_honors_test_sentinel(model_manager, monkeypatch):
    """`OMNIVOICE_MODEL=test` (the suite-wide sentinel from tests/conftest.py)
    must pass through verbatim — the #693 bare-token self-heal mapping it to
    the real k2-fsa/OmniVoice checkpoint is what let app-booting tests kick
    off a real multi-GB model download."""
    monkeypatch.setenv("OMNIVOICE_MODEL", "test")
    assert model_manager.resolve_omnivoice_checkpoint() == "test"

    # The #693 self-heal itself must keep working for actual engine-id leaks.
    monkeypatch.setenv("OMNIVOICE_MODEL", "omnivoice")
    assert (
        model_manager.resolve_omnivoice_checkpoint()
        == model_manager._DEFAULT_OMNIVOICE_CHECKPOINT
    )


def test_preload_never_loads_uninstalled_checkpoint(model_manager, monkeypatch):
    """Networked machine, repo exists on the Hub, model NOT installed locally:
    preload must skip. The old `model_info()` probe treated Hub reachability
    as "installed" and silently downloaded the full checkpoint in a
    background thread on every boot with an empty cache."""
    import huggingface_hub

    monkeypatch.setenv("OMNIVOICE_MODEL", "k2-fsa/OmniVoice")
    # Old-code determinism: make the Hub probe "succeed" without network.
    monkeypatch.setattr(
        huggingface_hub, "model_info", lambda *a, **k: object(), raising=False
    )
    monkeypatch.setattr(model_manager, "_checkpoint_in_local_cache", lambda c: False)

    loads = []

    async def _record_load():
        loads.append(True)
        return SimpleNamespace(llm=object())

    monkeypatch.setattr(model_manager, "_load_model_with_timeout", _record_load)
    asyncio.run(model_manager.preload_model())

    assert loads == [], "preload must never load/download an uninstalled checkpoint"
    assert model_manager.model is None


def test_preload_warms_up_locally_installed_checkpoint(model_manager, monkeypatch):
    """The counterpart guard: a locally present checkpoint must still warm up
    (skipping it would make the first /generate eat the full weight load)."""
    monkeypatch.setattr(model_manager, "_ram_available_bytes", lambda: 16 * 1024**3)
    monkeypatch.setattr(model_manager, "_checkpoint_in_local_cache", lambda c: True)

    loaded = SimpleNamespace(llm=object())

    async def _fake_load():
        return loaded

    monkeypatch.setattr(model_manager, "_load_model_with_timeout", _fake_load)
    asyncio.run(model_manager.preload_model())

    assert model_manager.model is loaded


# ── Engine-aware preload gate (3/9) ──────────────────────────────────────────


def test_preload_skips_when_active_engine_is_not_omnivoice(model_manager, monkeypatch):
    """auto mode + active engine 'vienue' → OmniVoice must NOT warm: on an
    8 GB box the warm-up held ~3 GB of VRAM from boot and engine_memory
    evicted it at the first non-OmniVoice generate anyway."""
    import services.tts_backend as tts_backend

    monkeypatch.setattr(tts_backend, "active_backend_id", lambda: "vienue")
    monkeypatch.setattr(model_manager, "_checkpoint_in_local_cache", lambda c: True)

    loads = []

    async def _record_load():
        loads.append(True)
        return SimpleNamespace(llm=object())

    monkeypatch.setattr(model_manager, "_load_model_with_timeout", _record_load)
    asyncio.run(model_manager.preload_model())

    assert loads == []
    assert model_manager.model is None


def test_preload_always_mode_overrides_engine_gate(model_manager, monkeypatch):
    """`always` is the user explicitly paying the VRAM cost — the engine gate
    must not apply."""
    monkeypatch.setenv("OMNIVOICE_PRELOAD_TTS", "always")
    import services.tts_backend as tts_backend

    monkeypatch.setattr(tts_backend, "active_backend_id", lambda: "vienue")
    monkeypatch.setattr(model_manager, "_checkpoint_in_local_cache", lambda c: True)

    loaded = SimpleNamespace(llm=object())

    async def _fake_load():
        return loaded

    monkeypatch.setattr(model_manager, "_load_model_with_timeout", _fake_load)
    asyncio.run(model_manager.preload_model())

    assert model_manager.model is loaded


def test_preload_ram_guard_skips_in_auto_mode(model_manager, monkeypatch):
    """auto mode + <4 GB available → skip (mirror of the capture-ASR RAM
    guard); the load path's own release handling stays responsible for the
    rest."""
    import psutil
    import services.tts_backend as tts_backend

    import services.tts_backend as tts_backend  # noqa: F811 — re-import ok

    monkeypatch.setattr(tts_backend, "active_backend_id", lambda: "omnivoice")
    monkeypatch.setattr(model_manager, "_checkpoint_in_local_cache", lambda c: True)
    monkeypatch.setattr(model_manager, "_ram_available_bytes", lambda: 1 * 1024**3)

    loads = []

    async def _record_load():
        loads.append(True)
        return SimpleNamespace(llm=object())

    monkeypatch.setattr(model_manager, "_load_model_with_timeout", _record_load)
    asyncio.run(model_manager.preload_model())

    assert loads == []
    assert model_manager.model is None


def test_preload_never_mode_skips_immediately(model_manager, monkeypatch):
    monkeypatch.setenv("OMNIVOICE_PRELOAD_TTS", "never")
    monkeypatch.setattr(model_manager, "_checkpoint_in_local_cache", lambda c: True)

    loads = []

    async def _record_load():
        loads.append(True)
        return SimpleNamespace(llm=object())

    monkeypatch.setattr(model_manager, "_load_model_with_timeout", _record_load)
    asyncio.run(model_manager.preload_model())

    assert loads == []
    assert model_manager.model is None
