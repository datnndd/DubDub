# -*- coding: utf-8 -*-
"""Unit tests for in-memory model cache, WAV validation, and amplitude normalization."""
import io
from pathlib import Path
from unittest.mock import MagicMock, patch
import wave
import numpy as np
import pytest
import soundfile as sf

from videotrans.services.model_cache import (
    get_cached_vieneu_engine,
    evict_vieneu_engine,
    get_cached_omnivoice_model,
    evict_omnivoice_model,
    clear_model_cache,
    _vieneu_cache,
    _omnivoice_cache,
)
from videotrans.services.voice_preview import (
    _is_valid_preview_wav,
    _run_vieneu_synthesis,
    _run_omnivoice_synthesis,
)


def test_is_valid_preview_wav(tmp_path: Path):
    non_existent = tmp_path / "does_not_exist.wav"
    assert not _is_valid_preview_wav(non_existent)

    zero_byte = tmp_path / "zero.wav"
    zero_byte.write_bytes(b"")
    assert not _is_valid_preview_wav(zero_byte)

    # Standard empty WAV header is 44 bytes
    header_only = tmp_path / "header_only.wav"
    header_only.write_bytes(b"RIFF" + b"\x00" * 40)
    assert len(header_only.read_bytes()) == 44
    assert not _is_valid_preview_wav(header_only)

    # Empty ffmpeg WAV with extra chunks (78 bytes) with 0 data frames
    ffmpeg_empty = tmp_path / "ffmpeg_empty.wav"
    header_78 = (
        b"RIFF\x46\x00\x00\x00WAVE"
        b"fmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00"
        b"LIST\x1a\x00\x00\x00INFOISFT\x0e\x00\x00\x00Lavf60.16.100\x00\x00"
        b"data\x00\x00\x00\x00"
    )
    ffmpeg_empty.write_bytes(header_78)
    assert len(header_78) >= 78
    assert ffmpeg_empty.stat().st_size > 44
    assert not _is_valid_preview_wav(ffmpeg_empty)

    # WAV with 1000 frames of pure digital silence (all zeros)
    silent_wav = tmp_path / "silent.wav"
    with wave.open(str(silent_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(b"\x00" * 4800)
    assert not _is_valid_preview_wav(silent_wav)

    # Valid audio WAV with actual audible sound
    valid_wav = tmp_path / "valid.wav"
    samples = (np.sin(np.linspace(0, 100, 2400)) * 0.5).astype(np.float32)
    sf.write(str(valid_wav), samples, 24000)
    assert valid_wav.stat().st_size > 44
    assert _is_valid_preview_wav(valid_wav)


def test_vieneu_model_cache_lifecycle():
    clear_model_cache()
    assert len(_vieneu_cache) == 0

    mock_engine = MagicMock()
    mock_engine.close = MagicMock()

    with patch("vieneu.Vieneu", return_value=mock_engine) as mock_cls:
        # First call creates and caches
        e1 = get_cached_vieneu_engine(device="cpu", backend="onnx")
        assert e1 is mock_engine
        assert mock_cls.call_count == 1

        # Second call returns cached instance without re-instantiation
        e2 = get_cached_vieneu_engine(device="cpu", backend="onnx")
        assert e2 is mock_engine
        assert mock_cls.call_count == 1

        # Evict device
        evict_vieneu_engine(device="cpu")
        mock_engine.close.assert_called_once()
        assert len(_vieneu_cache) == 0


def test_omnivoice_model_cache_lifecycle(tmp_path: Path):
    clear_model_cache()
    assert len(_omnivoice_cache) == 0

    model_dir = tmp_path / "models--k2-fsa--OmniVoice"
    model_dir.mkdir(parents=True)

    # If model.safetensors missing, raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        get_cached_omnivoice_model(model_dir=model_dir, device="cpu")

    # Create dummy model file
    (model_dir / "model.safetensors").write_bytes(b"dummy")

    mock_model = MagicMock()
    with patch("omnivoice.OmniVoice.from_pretrained", return_value=mock_model) as mock_load:
        m1 = get_cached_omnivoice_model(model_dir=model_dir, device="cpu")
        assert m1 is mock_model
        assert mock_load.call_count == 1

        # Second call reuses cached instance
        m2 = get_cached_omnivoice_model(model_dir=model_dir, device="cpu")
        assert m2 is mock_model
        assert mock_load.call_count == 1

        # Evict
        evict_omnivoice_model(model_dir=model_dir)
        assert len(_omnivoice_cache) == 0


def test_clear_model_cache_reclaims_all(tmp_path: Path):
    mock_v_engine = MagicMock()
    mock_omni_model = MagicMock()

    with patch("vieneu.Vieneu", return_value=mock_v_engine):
        get_cached_vieneu_engine(device="cpu", backend="onnx")

    m_dir = tmp_path / "dummy_omni"
    m_dir.mkdir()
    (m_dir / "model.safetensors").write_bytes(b"dummy")

    with patch("omnivoice.OmniVoice.from_pretrained", return_value=mock_omni_model):
        get_cached_omnivoice_model(model_dir=m_dir, device="cpu")

    assert len(_vieneu_cache) == 1
    assert len(_omnivoice_cache) == 1

    clear_model_cache()
    assert len(_vieneu_cache) == 0
    assert len(_omnivoice_cache) == 0


def test_run_vieneu_synthesis_peak_normalization(tmp_path: Path):
    out_file = tmp_path / "vieneu_out.wav"
    mock_engine = MagicMock()
    mock_engine.sample_rate = 24000
    # Simulate a faint signal with peak 0.05
    faint_signal = np.array([0.01, -0.05, 0.03, -0.02], dtype=np.float32)
    mock_engine.infer_batch.return_value = [faint_signal]

    with patch("videotrans.services.model_cache.get_cached_vieneu_engine", return_value=mock_engine):
        _run_vieneu_synthesis(
            output_file=out_file,
            text="Hello testing",
            use_cuda=False,
        )

    assert out_file.is_file()
    data, sr = sf.read(str(out_file))
    assert sr == 24000
    # Faint signal should have been boosted to ~0.90 peak
    assert pytest.approx(float(np.max(np.abs(data))), abs=1e-3) == 0.90


def test_run_vieneu_synthesis_rejects_silent_or_empty_audio(tmp_path: Path):
    out_file = tmp_path / "vieneu_empty.wav"
    mock_engine = MagicMock()
    mock_engine.sample_rate = 24000

    # Test 1: Empty audio array
    mock_engine.infer_batch.return_value = [np.array([], dtype=np.float32)]
    with patch("videotrans.services.model_cache.get_cached_vieneu_engine", return_value=mock_engine):
        with pytest.raises(RuntimeError, match="0 audio samples"):
            _run_vieneu_synthesis(output_file=out_file, text="Testing empty", use_cuda=False)

    # Test 2: Silent audio (< 1e-4)
    mock_engine.infer_batch.return_value = [np.zeros(1000, dtype=np.float32)]
    with patch("videotrans.services.model_cache.get_cached_vieneu_engine", return_value=mock_engine):
        with pytest.raises(RuntimeError, match="silent audio"):
            _run_vieneu_synthesis(output_file=out_file, text="Testing silent", use_cuda=False)


def test_run_vieneu_synthesis_detaches_tensor(tmp_path: Path):
    """Verify that PyTorch-like tensor outputs are detached to CPU numpy cleanly."""
    out_file = tmp_path / "vieneu_tensor.wav"
    mock_engine = MagicMock()
    mock_engine.sample_rate = 24000

    # Simulate a tensor object with .detach().cpu().numpy()
    class FakeTensor:
        def __init__(self, arr):
            self.arr = arr
        def detach(self):
            return self
        def cpu(self):
            return self
        def numpy(self):
            return self.arr

    faint = np.array([0.1, -0.4, 0.3, -0.2], dtype=np.float32)
    fake_t = FakeTensor(faint)
    mock_engine.infer_batch.return_value = [fake_t]

    with patch("videotrans.services.model_cache.get_cached_vieneu_engine", return_value=mock_engine):
        _run_vieneu_synthesis(
            output_file=out_file,
            text="Hello tensor",
            use_cuda=False,
        )

    assert out_file.is_file()
    data, sr = sf.read(str(out_file))
    assert sr == 24000
    assert pytest.approx(float(np.max(np.abs(data))), abs=1e-3) == 0.90


def test_voice_preview_cache_reuse_across_calls(tmp_path: Path, monkeypatch):
    """Verify that synthesize_voice_preview reuses cached audio without re-synthesizing."""
    import asyncio
    from videotrans.core import voice_store, db
    from videotrans.services.voice_preview import synthesize_voice_preview

    temp_db = tmp_path / "test_preview.db"
    db.init_db(temp_db)
    monkeypatch.setattr(voice_store, "db_conn", lambda p=None: db.db_conn(temp_db))
    monkeypatch.setattr(voice_store, "PREVIEWS_DIR", tmp_path / "previews")
    monkeypatch.setattr(voice_store, "VOICES_DIR", tmp_path / "voices")
    voice_store.init_voice_dirs()

    # Create dummy voice
    v = voice_store.create_voice(name="Cache Test Voice", provider=2, kind="clone", db_path=temp_db)
    v_id = v["id"]

    synthesizer_calls = []
    def fake_synth(voice_dict, p_path, sample_text):
        synthesizer_calls.append(voice_dict["id"])
        samples = (np.sin(np.linspace(0, 100, 2400)) * 0.5).astype(np.float32)
        sf.write(str(p_path), samples, 24000)

    from videotrans.services import voice_preview
    monkeypatch.setattr(voice_preview, "_preview_synthesizer", fake_synth)

    # First call: should synthesize and write file
    p1 = asyncio.run(synthesize_voice_preview(v_id, db_path=temp_db))
    assert p1.is_file()
    assert len(synthesizer_calls) == 1

    # Second call: must reuse cached preview WITHOUT calling synthesizer again
    p2 = asyncio.run(synthesize_voice_preview(v_id, db_path=temp_db))
    assert p2 == p1
    assert len(synthesizer_calls) == 1, "Cache was bypassed on second call!"


def test_custom_voices_preview_clone_alias(tmp_path: Path, monkeypatch):
    """Verify that POST /api/custom-voices/preview-clone works as an alias."""
    from fastapi.testclient import TestClient
    from videotrans.api.app import app
    from videotrans.services import voice_preview

    def fake_synth(voice_dict, p_path, sample_text):
        samples = (np.sin(np.linspace(0, 100, 2400)) * 0.5).astype(np.float32)
        sf.write(str(p_path), samples, 24000)

    monkeypatch.setattr(voice_preview, "_preview_synthesizer", fake_synth)

    dummy_audio = tmp_path / "ref.wav"
    sf.write(str(dummy_audio), np.sin(np.linspace(0, 50, 48000)), 24000)

    client = TestClient(app)
    with open(dummy_audio, "rb") as f:
        resp = client.post(
            "/api/custom-voices/preview-clone",
            data={"provider": "2", "text": "Testing alias", "language": "vi"},
            files={"audio": ("ref.wav", f, "audio/wav")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "preview_url" in data


def test_synthesize_clone_preview_timeout_fallback(tmp_path: Path, monkeypatch):
    """Verify synthesize_clone_preview recovers from timeout without throwing."""
    import asyncio
    from videotrans.services import voice_preview
    from videotrans.services.voice_preview import synthesize_clone_preview, _is_valid_preview_wav

    dummy_audio = tmp_path / "timeout_ref.wav"
    samples = (np.sin(np.linspace(0, 100, 48000)) * 0.5).astype(np.float32)
    sf.write(str(dummy_audio), samples, 24000)

    # Force synthesizer to simulate timeout
    async def fake_slow_synthesis(coro, *args, **kwargs):
        coro.close()
        raise asyncio.TimeoutError("Simulated slow synthesis")

    monkeypatch.setattr(voice_preview, "_preview_synthesizer", None)
    monkeypatch.setattr(asyncio, "wait_for", fake_slow_synthesis)

    pid, p_path = asyncio.run(synthesize_clone_preview(
        dummy_audio,
        provider=2,
        text="Testing timeout recovery",
        language="vi",
    ))
    assert p_path.is_file()
    assert _is_valid_preview_wav(p_path)


def test_api_preview_clone_handles_timeout(tmp_path: Path, monkeypatch):
    """Verify /api/voices/preview-clone returns 200 with fallback audio on synthesis timeout."""
    import asyncio
    from fastapi.testclient import TestClient
    from videotrans.api.app import app
    from videotrans.services import voice_preview

    dummy_audio = tmp_path / "api_timeout_ref.wav"
    samples = (np.sin(np.linspace(0, 100, 48000)) * 0.5).astype(np.float32)
    sf.write(str(dummy_audio), samples, 24000)

    async def fake_slow_synthesis(coro, *args, **kwargs):
        coro.close()
        raise asyncio.TimeoutError("Model took too long")

    monkeypatch.setattr(voice_preview, "_preview_synthesizer", None)
    monkeypatch.setattr(asyncio, "wait_for", fake_slow_synthesis)

    client = TestClient(app)
    with open(dummy_audio, "rb") as f:
        resp = client.post(
            "/api/voices/preview-clone",
            data={"provider": "2", "text": "Timeout test", "language": "vi"},
            files={"audio": ("ref.wav", f, "audio/wav")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "preview_url" in data


def test_unified_tts_preview_with_custom_voice_and_api(tmp_path: Path, monkeypatch):
    """Verify POST /api/tts/preview and GET /api/tts/preview/{id}/audio work with custom voices."""
    import asyncio
    from fastapi.testclient import TestClient
    from videotrans.api.app import app
    from videotrans.core import voice_store, db
    from videotrans.services import voice_preview
    from videotrans.services.voice_preview import synthesize_unified_tts_preview

    temp_db = tmp_path / "unified_test.db"
    db.init_db(temp_db)
    monkeypatch.setattr(voice_store, "db_conn", lambda p=None: db.db_conn(temp_db))
    monkeypatch.setattr(voice_store, "PREVIEWS_DIR", tmp_path / "previews")
    monkeypatch.setattr(voice_store, "VOICES_DIR", tmp_path / "voices")
    voice_store.init_voice_dirs()

    # Create dummy reference audio file
    ref_audio = tmp_path / "voices" / "custom_ref.wav"
    samples = (np.sin(np.linspace(0, 100, 24000)) * 0.5).astype(np.float32)
    sf.write(str(ref_audio), samples, 24000)

    # Create custom voice in DB
    v = voice_store.create_voice(
        name="Lab Custom Voice",
        provider=2,
        kind="clone",
        ref_audio_path="custom_ref.wav",
        db_path=temp_db,
    )
    v_id = v["id"]

    synthesizer_calls = []
    def fake_synth(voice_dict, p_path, sample_text):
        synthesizer_calls.append((voice_dict["id"], sample_text))
        out_samples = (np.sin(np.linspace(0, 50, 4800)) * 0.4).astype(np.float32)
        sf.write(str(p_path), out_samples, 24000)

    monkeypatch.setattr(voice_preview, "_preview_synthesizer", fake_synth)

    # Direct function test
    p_id, p_path, _ = asyncio.run(
        synthesize_unified_tts_preview(
            provider=2,
            voice=v_id,
            text="Testing custom voice in lab",
            style="doc_truyen",
            tuning_params={"temperature": 0.95},
            db_path=temp_db,
        )
    )
    assert p_path.is_file()
    assert len(synthesizer_calls) == 1
    assert synthesizer_calls[0][1] == "Testing custom voice in lab"

    # API route test
    client = TestClient(app)
    resp = client.post(
        "/api/tts/preview",
        json={
            "voice": v_id,
            "provider": 2,
            "text": "Testing custom voice via API",
            "style": "tin_tuc",
            "tuning_params": {"temperature": 0.75},
        },
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["ok"] is True
    assert "preview_url" in res_data
    audio_endpoint = res_data["preview_url"]

    # Verify audio GET endpoint
    audio_resp = client.get(audio_endpoint)
    assert audio_resp.status_code == 200
    assert audio_resp.headers.get("content-type") == "audio/wav"
    assert "no-cache" in audio_resp.headers.get("cache-control", "")
    assert len(audio_resp.content) > 44




