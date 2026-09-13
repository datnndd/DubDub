"""Phase 3 — TTS / ASR / LLM adapter registries under 7-provider boundary."""
import os
os.environ.setdefault("OMNIVOICE_DISABLE_FILE_LOG", "1")

import sys
import types

import pytest
from services import tts_backend, asr_backend, llm_backend


# ── TTS ─────────────────────────────────────────────────────────────────────


def test_tts_registry_lists_all_backends():
    rows = tts_backend.list_backends()
    ids = {r["id"] for r in rows}
    assert ids == {"omnivoice", "vienue"}
    for r in rows:
        assert set(r) >= {"id", "display_name", "available", "reason"}


def test_tts_active_backend_defaults_to_omnivoice(monkeypatch):
    monkeypatch.delenv("OMNIVOICE_TTS_BACKEND", raising=False)
    from core import prefs as _prefs
    _prefs.set_("tts_backend", "omnivoice")
    assert tts_backend.active_backend_id() == "omnivoice"


def test_tts_active_backend_env_override(monkeypatch):
    monkeypatch.setenv("OMNIVOICE_TTS_BACKEND", "vienue")
    assert tts_backend.active_backend_id() == "vienue"
    monkeypatch.delenv("OMNIVOICE_TTS_BACKEND", raising=False)


def test_tts_unknown_backend_raises():
    with pytest.raises(ValueError):
        tts_backend.get_backend_class("not-a-real-one")


def test_tts_sample_rate_omnivoice():
    assert tts_backend.OmniVoiceBackend().sample_rate == 24000


# ── ASR ─────────────────────────────────────────────────────────────────────


def test_asr_registry_lists_deepgram():
    rows = asr_backend.list_backends()
    ids = {r["id"] for r in rows}
    assert ids == {"deepgram-asr"}
    for r in rows:
        assert set(r) >= {"id", "display_name", "available"}


def test_asr_active_backend_id_is_deepgram():
    assert asr_backend.active_backend_id() == "deepgram-asr"
    assert isinstance(asr_backend.get_active_asr_backend(), asr_backend.DeepgramASRBackend)


def test_asr_auto_detect_is_deepgram():
    assert asr_backend._auto_detect() == "deepgram-asr"


# ── LLM ─────────────────────────────────────────────────────────────────────


def test_llm_registry_includes_off():
    rows = llm_backend.list_backends()
    ids = {r["id"] for r in rows}
    assert ids == {"openai-compat", "off"}


def test_llm_off_chat_raises_actionable(monkeypatch):
    monkeypatch.setenv("OMNIVOICE_LLM_BACKEND", "off")
    be = llm_backend.get_active_llm_backend()
    assert isinstance(be, llm_backend.OffBackend)
    with pytest.raises(RuntimeError) as ei:
        be.chat(system="x", user="y")
    assert "TRANSLATE_BASE_URL" in str(ei.value)


def test_llm_auto_selects_off_when_nothing_configured(clean_llm_env):
    assert llm_backend.active_backend_id() == "off"


def test_llm_auto_selects_openai_compat_when_configured(monkeypatch):
    monkeypatch.delenv("OMNIVOICE_LLM_BACKEND", raising=False)
    monkeypatch.setenv("TRANSLATE_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("TRANSLATE_API_KEY", "local")
    try:
        import openai  # noqa: F401
    except ImportError:
        pytest.skip("openai package not available in this environment")
    assert llm_backend.active_backend_id() == "openai-compat"


# ── HF Hub closed-client recovery (#880) ────────────────────────────────────


def test_hf_retry_recovers_from_closed_client_once():
    calls = []

    def loader():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("Cannot send a request, as the client has been closed.")
        return "model"

    assert tts_backend._retry_once_with_fresh_hf_client(loader, what="test") == "model"
    assert len(calls) == 2


def test_hf_retry_does_not_retry_unrelated_errors():
    calls = []

    def loader():
        calls.append(1)
        raise ValueError("bad checkpoint id")

    with pytest.raises(ValueError):
        tts_backend._retry_once_with_fresh_hf_client(loader, what="test")
    assert len(calls) == 1


def test_hf_retry_is_single_shot():
    calls = []

    def loader():
        calls.append(1)
        raise RuntimeError("Cannot send a request, as the client has been closed.")

    with pytest.raises(RuntimeError):
        tts_backend._retry_once_with_fresh_hf_client(loader, what="test")
    assert len(calls) == 2
