"""VieNeu-TTS engine scaffold.

Opt-in (subprocess-isolated, own venv) and completely inert on a default
install — never importing the upstream package, never reporting available
without a venv. These tests pin exactly that, plus the generate() kwarg
arbitration the voice-management UI relies on.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))


def test_registered_in_lazy_registry():
    from services.tts_backend import _LAZY_REGISTRY
    assert _LAZY_REGISTRY.get("vienue") == ("engines.vienue", "VieNueBackend")


def test_backend_class_metadata():
    from engines.vienue import VieNueBackend
    assert VieNueBackend.id == "vienue"
    assert VieNueBackend.gpu_compat == ("cuda", "cpu")  # ONNX CPU / CUDA; no MPS claim
    assert VieNueBackend.supports_voice_design is False
    assert VieNueBackend.supports_cloning is True
    assert VieNueBackend._DEFAULT_SAMPLE_RATE == 48000


def test_default_language_is_vietnamese():
    from engines.vienue import VieNueBackend
    assert VieNueBackend().supported_languages == ["vi"]


def test_language_env_override(monkeypatch):
    monkeypatch.setenv("OMNIVOICE_VIENEU_LANGUAGES", "vi,en")
    from engines.vienue import VieNueBackend
    assert VieNueBackend().supported_languages == ["vi", "en"]


def test_inert_without_venv(monkeypatch, tmp_path):
    # Hermetic: point the package-owned venv at a nonexistent tmp dir — a dev
    # machine that already installed vieneu has a real .venv on disk.
    from engines.vienue import bootstrap, VieNueBackend
    monkeypatch.setattr(bootstrap, "_ENGINES_VENV_DIR", tmp_path / ".venv")
    monkeypatch.delenv("OMNIVOICE_VIENEU_VENV", raising=False)
    bootstrap.invalidate()
    assert bootstrap.is_vieneu_installed() is False

    ok, reason = VieNueBackend.is_available()
    assert ok is False
    assert "vieneu" in reason
    assert "uv" in reason  # the fix must name the tool


def test_sidecar_spec_registered():
    """Phase 2 — the engine is one-click installable: a pip-package
    SidecarSpec exists and points the engine's own bootstrap env var at the
    provisioned venv."""
    from services.sidecar_install import get_spec
    spec = get_spec("vienue")
    assert spec is not None
    assert spec.pip_requirement == "vieneu>=3.0"
    assert spec.env_var == "OMNIVOICE_VIENEU_VENV"
    assert spec.probe_module == "vieneu"
    assert spec.weights_repo_id is None  # weights download lazily inside the SDK


def test_one_click_install_and_languages_reach_list_backends():
    from services.tts_backend import list_backends
    row = next(r for r in list_backends() if r["id"] == "vienue")
    assert row["one_click_install"] is True
    assert row["languages"] == ["vi"]


def test_resolve_without_uv_is_actionable(monkeypatch, tmp_path):
    """No venv + no uv → a RuntimeError naming the fix (uv), not a traceback."""
    # Hermetic: a dev machine that already installed vieneu has a real
    # package-owned .venv on disk — point it at a nonexistent tmp dir.
    from engines.vienue import bootstrap
    monkeypatch.setattr(bootstrap, "_ENGINES_VENV_DIR", tmp_path / ".venv")
    monkeypatch.delenv("OMNIVOICE_VIENEU_VENV", raising=False)
    bootstrap.invalidate()
    monkeypatch.setattr(bootstrap, "_locate_uv", lambda: None)
    import pytest
    with pytest.raises(RuntimeError, match="uv"):
        bootstrap.resolve_vieneu_venv()


def _capture_generate(monkeypatch):
    """Stub SubprocessBackend.generate and return (calls, instance)."""
    from engines.vienue import VieNueBackend
    from services.subprocess_backend import SubprocessBackend
    calls = []

    def _fake(self, text, **kw):
        calls.append({"text": text, **kw})
        return "AUDIO"

    monkeypatch.setattr(SubprocessBackend, "generate", _fake)
    return calls, VieNueBackend()


def test_generate_forwards_clone_kwargs(monkeypatch):
    calls, backend = _capture_generate(monkeypatch)
    out = backend.generate(
        "Xin chào", ref_audio="C:/refs/me.wav", ref_text="Xin chào thế giới",
        language="vi", seed=42, instruct="gender: male", num_step=16,
    )
    assert out == "AUDIO"
    assert calls == [{
        "text": "Xin chào",
        "ref_audio": "C:/refs/me.wav",
        "ref_text": "Xin chào thế giới",
        "language": "vi",
        "seed": 42,
    }]


def test_generate_rejects_unsupported_language_before_spawning(monkeypatch):
    """language=en on a vi-only engine → ValueError parent-side (so
    _language_rejection_or rewrites it with the engine name + the way out)
    and NOTHING reaches the sidecar — previously the request spawned the
    sidecar, died opaquely, and the user saw the generic 'Generation failed'."""
    import pytest

    calls, backend = _capture_generate(monkeypatch)
    with pytest.raises(ValueError, match="language not supported"):
        backend.generate("Hello world", language="en")
    assert calls == []


def test_generate_ignores_unsupported_params_without_ref(monkeypatch):
    """No ref → no ref_audio/ref_text on the wire; unsupported params dropped
    (never crash the request); plain text still synthesizes."""
    calls, backend = _capture_generate(monkeypatch)
    out = backend.generate("Chỉ mình thôi", instruct="style: urgent", description="deep voice")
    assert out == "AUDIO"
    assert calls == [{"text": "Chỉ mình thôi"}]


def test_generate_drops_stray_ref_text_without_ref_audio(monkeypatch):
    """ref_text alone cannot clone — dropped rather than confusing the sidecar."""
    calls, backend = _capture_generate(monkeypatch)
    backend.generate("Xin chào", ref_text="orphan transcript")
    assert calls == [{"text": "Xin chào"}]
