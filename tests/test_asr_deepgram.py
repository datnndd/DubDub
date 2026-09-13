"""Deepgram Cloud ASR backend tests.

Verifies:
- is_available() gating (needs API key)
- gpu_compat = ("cpu",) — zero local VRAM/RAM
- Deepgram JSON response adaptation into VoiceStudio standard chunks & segments with speaker turns
- Reachability / auth probe
- Settings router endpoints (GET, PUT, POST /test)
"""
from __future__ import annotations

import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

os.environ.setdefault("OMNIVOICE_MODEL", "test")
os.environ.setdefault("OMNIVOICE_DISABLE_FILE_LOG", "1")


@pytest.fixture
def ss(monkeypatch):
    """services.settings_store in-memory fixture."""
    from services import settings_store as _ss

    text: dict[str, str] = {}
    secrets: dict[str, str] = {}
    monkeypatch.setattr(_ss, "get_text", lambda k, default=None: text.get(k, default))
    monkeypatch.setattr(_ss, "set_text", lambda k, v: text.__setitem__(k, v))
    monkeypatch.setattr(_ss, "get_secret", lambda n: secrets.get(n))
    monkeypatch.setattr(
        _ss, "set_secret", lambda n, v: secrets.__setitem__(n, v) if v else secrets.pop(n, None)
    )
    monkeypatch.setattr(_ss, "list_secret_names", lambda: list(secrets))
    return _ss


@pytest.fixture
def asr_mod(ss, monkeypatch):
    """services.asr_backend with settings_store in-memory."""
    for var in ("DEEPGRAM_API_KEY", "DEEPGRAM_MODEL"):
        monkeypatch.delenv(var, raising=False)
    import importlib
    return importlib.import_module("services.asr_backend")


@pytest.fixture
def settings_mod(asr_mod):
    """api.routers.settings sharing the same monkeypatched settings_store."""
    import importlib
    return importlib.import_module("api.routers.settings")


# ── is_available() gating & metadata ──────────────────────────────────────────


def test_unavailable_without_api_key(asr_mod):
    ok, msg = asr_mod.DeepgramASRBackend.is_available()
    assert ok is False
    assert "Model Catalogue → Engines" in msg


def test_available_once_api_key_configured(asr_mod, ss):
    ss.set_secret(asr_mod._ASR_DEEPGRAM_SECRET_NAME, "test-deepgram-key-12345")
    ok, msg = asr_mod.DeepgramASRBackend.is_available()
    assert ok is True
    assert msg == "ready"


def test_gpu_compat_is_cpu_only(asr_mod):
    assert asr_mod.DeepgramASRBackend.gpu_compat == ("cpu",)


def test_deepgram_registered_in_registry(asr_mod):
    assert "deepgram-asr" in asr_mod._REGISTRY
    assert asr_mod._REGISTRY["deepgram-asr"] is asr_mod.DeepgramASRBackend


# ── Response adaptation ───────────────────────────────────────────────────────


def test_transcribe_adapts_utterances_with_diarization(asr_mod, ss, monkeypatch, tmp_path):
    ss.set_secret(asr_mod._ASR_DEEPGRAM_SECRET_NAME, "test-key")

    mock_resp_data = {
        "results": {
            "channels": [{"alternatives": [{"languages": ["en"], "transcript": "Hello world"}]}],
            "utterances": [
                {
                    "start": 0.0,
                    "end": 1.5,
                    "transcript": "Hello world",
                    "speaker": 0,
                    "words": [
                        {"word": "Hello", "start": 0.0, "end": 0.6, "confidence": 0.99},
                        {"word": "world", "start": 0.7, "end": 1.5, "confidence": 0.98},
                    ],
                },
                {
                    "start": 2.0,
                    "end": 3.5,
                    "transcript": "How are you?",
                    "speaker": 1,
                    "words": [
                        {"word": "How", "start": 2.0, "end": 2.3, "confidence": 0.95},
                        {"word": "are", "start": 2.4, "end": 2.7, "confidence": 0.96},
                        {"word": "you?", "start": 2.8, "end": 3.5, "confidence": 0.97},
                    ],
                },
            ],
        }
    }

    class _MockResponse:
        status_code = 200
        text = "{}"
        def json(self):
            return mock_resp_data

    class _MockHttpxClient:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, **kwargs):
            return _MockResponse()

    import httpx
    monkeypatch.setattr(httpx, "Client", _MockHttpxClient)

    audio = tmp_path / "test.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")

    backend = asr_mod.DeepgramASRBackend()
    out = backend.transcribe(str(audio))

    assert out["language"] == "en"
    assert len(out["segments"]) == 2
    assert out["segments"][0]["text"] == "Hello world"
    assert out["segments"][0]["speaker"] == "Speaker 1"
    assert out["segments"][0]["words"][0]["word"] == "Hello"
    assert out["segments"][1]["text"] == "How are you?"
    assert out["segments"][1]["speaker"] == "Speaker 2"
    assert out["chunks"] == [
        {"text": "Hello world", "timestamp": (0.0, 1.5)},
        {"text": "How are you?", "timestamp": (2.0, 3.5)},
    ]


def test_transcribe_fallback_when_utterances_empty(asr_mod, ss, monkeypatch, tmp_path):
    ss.set_secret(asr_mod._ASR_DEEPGRAM_SECRET_NAME, "test-key")

    mock_resp_data = {
        "results": {
            "channels": [
                {
                    "alternatives": [
                        {
                            "transcript": "Fallback audio text",
                            "languages": ["vi"],
                            "words": [
                                {"word": "Fallback", "start": 0.0, "end": 0.5, "speaker": 0},
                                {"word": "audio", "start": 0.6, "end": 1.0, "speaker": 0},
                                {"word": "text", "start": 1.1, "end": 1.5, "speaker": 0},
                            ],
                        }
                    ]
                }
            ],
            "utterances": [],
        }
    }

    class _MockResponse:
        status_code = 200
        text = "{}"
        def json(self):
            return mock_resp_data

    class _MockHttpxClient:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, **kwargs):
            return _MockResponse()

    import httpx
    monkeypatch.setattr(httpx, "Client", _MockHttpxClient)

    audio = tmp_path / "test.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")

    backend = asr_mod.DeepgramASRBackend()
    out = backend.transcribe(str(audio))

    assert out["language"] == "vi"
    assert len(out["segments"]) == 1
    assert out["segments"][0]["text"] == "Fallback audio text"
    assert len(out["segments"][0]["words"]) == 3
    assert out["chunks"] == [{"text": "Fallback audio text", "timestamp": (0.0, 1.5)}]


# ── Probe tests ───────────────────────────────────────────────────────────────


def test_probe_deepgram_not_configured(asr_mod):
    res = asr_mod.probe_deepgram_server()
    assert res["ok"] is False
    assert res["status"] == "not_configured"


def test_probe_deepgram_ok(asr_mod, monkeypatch):
    class _MockResp:
        status_code = 200

    class _MockClient:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, **kwargs):
            return _MockResp()

    import httpx
    monkeypatch.setattr(httpx, "Client", _MockClient)

    res = asr_mod.probe_deepgram_server(api_key="valid-key")
    assert res["ok"] is True
    assert res["status"] == "ok"


def test_probe_deepgram_auth_failed(asr_mod, monkeypatch):
    class _MockResp:
        status_code = 401
        text = "Invalid credentials"

    class _MockClient:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, **kwargs):
            return _MockResp()

    import httpx
    monkeypatch.setattr(httpx, "Client", _MockClient)

    res = asr_mod.probe_deepgram_server(api_key="bad-key")
    assert res["ok"] is False
    assert res["status"] == "auth_failed"


# ── Settings router tests ─────────────────────────────────────────────────────


def test_settings_router_get_and_put(settings_mod, ss):
    # Initial state
    state = settings_mod.get_asr_deepgram()
    assert state["model"] == "nova-2"
    assert state["has_key"] is False

    # Update model and set API key
    body = settings_mod._ASRDeepgramBody(model="nova-3", api_key="secret-dg-key")
    updated = settings_mod.set_asr_deepgram(body)
    assert updated["model"] == "nova-3"
    assert updated["has_key"] is True

    # Check that key is not leaked in plain text
    res = settings_mod.get_asr_deepgram()
    assert res["model"] == "nova-3"
    assert res["has_key"] is True
    assert "secret-dg-key" not in str(res)

    # Clearing key
    body_clear = settings_mod._ASRDeepgramBody(api_key="")
    cleared = settings_mod.set_asr_deepgram(body_clear)
    assert cleared["has_key"] is False


def test_deepgram_transcribe_with_language_parameter(asr_mod, ss, monkeypatch, tmp_path):
    ss.set_secret(asr_mod._ASR_DEEPGRAM_SECRET_NAME, "test-key")
    captured_params = {}

    class _MockResponse:
        status_code = 200
        def json(self):
            return {
                "results": {
                    "channels": [{"alternatives": [{"languages": ["vi"], "transcript": "Xin chào"}]}],
                    "utterances": [
                        {
                            "start": 0.0,
                            "end": 1.0,
                            "transcript": "Xin chào",
                            "speaker": 0,
                            "words": [{"word": "Xin", "start": 0.0, "end": 0.4}, {"word": "chào", "start": 0.5, "end": 1.0}],
                        }
                    ],
                }
            }

    class _MockHttpxClient:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, params=None, **kwargs):
            captured_params.update(params or {})
            return _MockResponse()

    import httpx
    monkeypatch.setattr(httpx, "Client", _MockHttpxClient)

    audio = tmp_path / "test.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")

    backend = asr_mod.DeepgramASRBackend()
    backend.transcribe(str(audio), language="vi")

    assert captured_params.get("language") == "vi"
    assert "detect_language" not in captured_params

    # cmn-Hans -> zh-CN
    captured_params.clear()
    backend.transcribe(str(audio), language="cmn-Hans")
    assert captured_params.get("language") == "zh-CN"

    # cmn-Hant -> zh-TW
    captured_params.clear()
    backend.transcribe(str(audio), language="cmn-Hant")
    assert captured_params.get("language") == "zh-TW"

    # Auto language
    captured_params.clear()
    backend.transcribe(str(audio), language="auto")
    assert captured_params.get("detect_language") == "true"
    assert "language" not in captured_params


def test_deepgram_transcribe_error_includes_api_response_detail(asr_mod, ss, monkeypatch, tmp_path):
    ss.set_secret(asr_mod._ASR_DEEPGRAM_SECRET_NAME, "test-key")

    class _MockErrorResponse:
        status_code = 400
        text = '{"err_code":"INVALID_PARAM","err_msg":"Language detection not supported"}'

    class _MockHttpxClient:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, **kwargs):
            return _MockErrorResponse()

    import httpx
    monkeypatch.setattr(httpx, "Client", _MockHttpxClient)

    audio = tmp_path / "test.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")

    backend = asr_mod.DeepgramASRBackend()
    with pytest.raises(RuntimeError) as exc_info:
        backend.transcribe(str(audio))

    assert "Deepgram API error (400)" in str(exc_info.value)
    assert "Language detection not supported" in str(exc_info.value)


def test_deepgram_transcribe_picks_up_late_configured_key(asr_mod, ss, monkeypatch, tmp_path):
    # Initialized without key
    backend = asr_mod.DeepgramASRBackend()

    class _MockOkResponse:
        status_code = 200
        text = "{}"
        def json(self):
            return {"results": {"channels": [{"alternatives": [{"transcript": "hello"}]}]}}

    captured_headers = {}
    class _MockHttpxClient:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, headers=None, **kwargs):
            captured_headers.update(headers or {})
            return _MockOkResponse()

    import httpx
    monkeypatch.setattr(httpx, "Client", _MockHttpxClient)

    # Save key after backend creation
    ss.set_secret(asr_mod._ASR_DEEPGRAM_SECRET_NAME, "late-configured-key")

    audio = tmp_path / "test.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")

    res = backend.transcribe(str(audio))
    assert res["chunks"][0]["text"] == "hello"
    assert captured_headers.get("Authorization") == "Token late-configured-key"


