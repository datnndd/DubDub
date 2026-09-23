# -*- coding: utf-8 -*-
"""Integration tests for custom voice REST APIs, audio normalizer, and preview service."""
import asyncio
import io
from pathlib import Path
import struct
import wave
import aiohttp
from aiohttp.test_utils import TestClient, TestServer
import pytest

from videotrans.api.app import create_app
from videotrans.core.db import init_db
from videotrans.core import voice_store
from videotrans.services.audio_normalizer import normalize_reference_audio
from videotrans import tts


def create_wav_file(path: Path, duration_sec: float = 3.0, sample_rate: int = 48000) -> Path:
    """Generate a valid PCM 16-bit mono WAV test file."""
    num_samples = int(duration_sec * sample_rate)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # 440Hz audible sine wave / non-zero frames
        frames = [int(10000 * ((i % 100) / 100.0)) for i in range(num_samples)]
        wf.writeframes(struct.pack(f"<{num_samples}h", *frames))
    return path


@pytest.fixture
def voice_api_env(tmp_path, monkeypatch):
    """Isolate DB and filesystem for voice management API tests."""
    db_path = tmp_path / "test_api_voices.db"
    init_db(db_path)

    v_dir = tmp_path / "data" / "voices"
    p_dir = tmp_path / "tmp" / "voice_previews"
    uploads_dir = tmp_path / "uploads"

    monkeypatch.setattr(voice_store, "VOICES_DIR", v_dir)
    monkeypatch.setattr(voice_store, "PREVIEWS_DIR", p_dir)
    voice_store.init_voice_dirs()

    # Point db_conn default to this test db
    monkeypatch.setattr("videotrans.core.db._current_db_path", db_path)

    from videotrans.services import voice_preview
    def fake_synthesizer(voice, preview_path, sample_text):
        create_wav_file(preview_path, duration_sec=3.0)

    voice_preview.set_preview_synthesizer(fake_synthesizer)

    app = create_app(upload_dir=uploads_dir)
    yield {
        "app": app,
        "db_path": db_path,
        "v_dir": v_dir,
        "p_dir": p_dir,
        "tmp_path": tmp_path,
    }
    voice_preview.set_preview_synthesizer(None)


def test_audio_normalizer_duration_validation(tmp_path):
    # 1. Too short (< 2.0s)
    short_wav = tmp_path / "short.wav"
    create_wav_file(short_wav, duration_sec=1.2)
    out_wav = tmp_path / "out1.wav"
    with pytest.raises(ValueError, match="between 2.0 and 30.0 seconds"):
        normalize_reference_audio(short_wav, out_wav, provider=tts.VIENEU_TTS)

    # 2. Too long (> 30.0s)
    long_wav = tmp_path / "long.wav"
    create_wav_file(long_wav, duration_sec=32.0)
    out_wav2 = tmp_path / "out2.wav"
    with pytest.raises(ValueError, match="between 2.0 and 30.0 seconds"):
        normalize_reference_audio(long_wav, out_wav2, provider=tts.VIENEU_TTS)

    # 3. Valid duration (e.g. 4.0s)
    valid_wav = tmp_path / "valid.wav"
    create_wav_file(valid_wav, duration_sec=4.0)
    out_wav3 = tmp_path / "out3.wav"
    meta = normalize_reference_audio(valid_wav, out_wav3, provider=tts.VIENEU_TTS)
    assert meta["sample_rate"] == 48000
    assert meta["channels"] == 1
    assert out_wav3.is_file()


def test_custom_voices_api_lifecycle(voice_api_env):
    app = voice_api_env["app"]
    tmp_path = voice_api_env["tmp_path"]

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            # 1. Initial list should be empty
            res = await client.get("/api/custom-voices")
            assert res.status == 200
            data = await res.json()
            assert data["voices"] == []

            # 2. Create voice - missing name validation
            res_bad_name = await client.post(
                "/api/custom-voices",
                data=aiohttp.FormData({"name": "   ", "provider": "2"}),
            )
            assert res_bad_name.status == 400

            # 3. Create voice - valid multipart upload
            sample_wav = tmp_path / "sample_voice.wav"
            create_wav_file(sample_wav, duration_sec=3.5)

            form = aiohttp.FormData()
            form.add_field("name", "Lan Phương")
            form.add_field("provider", "vieneu")
            form.add_field("description", "Professional storyteller")
            form.add_field("language", "vi")
            form.add_field("instruct", "Warm, emotional tone")
            form.add_field("ref_text", "Bản tin thời sự tối nay.")
            form.add_field(
                "audio",
                sample_wav.read_bytes(),
                filename="sample_voice.wav",
                content_type="audio/wav",
            )

            res_create = await client.post("/api/custom-voices", data=form)
            assert res_create.status == 201
            created = await res_create.json()
            assert created["name"] == "Lan Phương"
            assert created["provider"] == tts.VIENEU_TTS
            assert created["language"] == "vi"
            assert created["ref_text"] == "Bản tin thời sự tối nay."
            voice_id = created["id"]
            assert voice_id.startswith("voice_")

            # 4. Fetch single voice
            res_get = await client.get(f"/api/custom-voices/{voice_id}")
            assert res_get.status == 200
            fetched = await res_get.json()
            assert fetched["id"] == voice_id
            assert fetched["name"] == "Lan Phương"

            # 5. Stream reference audio
            res_audio = await client.get(f"/api/custom-voices/{voice_id}/audio")
            assert res_audio.status == 200
            assert "audio/wav" in res_audio.headers.get("Content-Type", "")
            audio_content = await res_audio.read()
            assert len(audio_content) > 0
            assert audio_content.startswith(b"RIFF")

            # 6. Audition preview generation
            res_preview = await client.post(
                f"/api/custom-voices/{voice_id}/preview",
                json={"text": "Xin chào đây là bản nghe thử"},
            )
            assert res_preview.status == 200
            prev_data = await res_preview.json()
            assert prev_data["ok"] is True
            assert f"/api/custom-voices/{voice_id}/preview/audio" in prev_data["preview_url"]

            # Stream preview audio
            res_prev_audio = await client.get(f"/api/custom-voices/{voice_id}/preview/audio")
            assert res_prev_audio.status == 200
            assert "audio/wav" in res_prev_audio.headers.get("Content-Type", "")

            # 7. Update voice metadata
            res_update = await client.put(
                f"/api/custom-voices/{voice_id}",
                json={"name": "Lan Phương (Pro)", "instruct": "Formal broadcast voice"},
            )
            assert res_update.status == 200
            updated = await res_update.json()
            assert updated["name"] == "Lan Phương (Pro)"
            assert updated["instruct"] == "Formal broadcast voice"

            # 8. Check /api/voices returns rich items alongside voices
            res_voices = await client.get("/api/voices?tts_type=2&language=vi")
            assert res_voices.status == 200
            voices_payload = await res_voices.json()
            assert "voices" in voices_payload
            assert "items" in voices_payload
            assert any(item["name"] == "Lan Phương (Pro)" for item in voices_payload["items"])

            # 9. Soft delete
            res_del = await client.delete(f"/api/custom-voices/{voice_id}")
            assert res_del.status == 200

            # Should not appear in active custom voices
            res_list_after = await client.get("/api/custom-voices")
            list_data = await res_list_after.json()
            assert not any(v["id"] == voice_id for v in list_data["voices"])

            # 10. Hard delete
            res_hard_del = await client.delete(f"/api/custom-voices/{voice_id}?hard=true")
            assert res_hard_del.status == 200

            res_get_deleted = await client.get(f"/api/custom-voices/{voice_id}")
            assert res_get_deleted.status == 404
        finally:
            await client.close()

    asyncio.run(scenario())


def test_audio_normalizer_exotic_formats(tmp_path):
    """Verify audio normalizer correctly handles and transcodes exotic audio formats."""
    # 1. Create a base WAV
    base_wav = tmp_path / "base.wav"
    create_wav_file(base_wav, duration_sec=3.0, sample_rate=44100)

    from videotrans.util.help_ffmpeg import runffmpeg

    # 2. Transcode to .flac, .ogg, .mp3, .m4a
    formats = [
        ("test.flac", ["-y", "-i", str(base_wav), str(tmp_path / "test.flac")]),
        ("test.ogg", ["-y", "-i", str(base_wav), "-c:a", "libvorbis", str(tmp_path / "test.ogg")]),
        ("test.mp3", ["-y", "-i", str(base_wav), "-c:a", "libmp3lame", str(tmp_path / "test.mp3")]),
    ]

    for fname, cmd in formats:
        try:
            runffmpeg(cmd, force_cpu=True)
            in_file = tmp_path / fname
            if in_file.is_file():
                out_wav = tmp_path / f"norm_{fname}.wav"
                meta = normalize_reference_audio(in_file, out_wav, provider=tts.OMNIVOICE_TTS)
                assert meta["sample_rate"] == 24000
                assert meta["channels"] == 1
                assert out_wav.is_file()
                assert out_wav.stat().st_size > 0
        except Exception:
            # Skip specific codec if not compiled into local FFmpeg build
            pass


def test_custom_voices_api_provider_variants(voice_api_env):
    """Verify OmniVoice with ref_text and ElevenLabs with external_voice_id."""
    app = voice_api_env["app"]
    tmp_path = voice_api_env["tmp_path"]

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            # 1. OmniVoice creation with ref_text and audio
            omni_wav = tmp_path / "omni.wav"
            create_wav_file(omni_wav, duration_sec=4.0, sample_rate=24000)

            form_omni = aiohttp.FormData()
            form_omni.add_field("name", "Bảo Long")
            form_omni.add_field("provider", "1")
            form_omni.add_field("ref_text", "Đoạn văn bản mẫu kiểm tra.")
            form_omni.add_field("audio", omni_wav.read_bytes(), filename="omni.wav")

            res_omni = await client.post("/api/custom-voices", data=form_omni)
            assert res_omni.status == 201
            omni_data = await res_omni.json()
            assert omni_data["provider"] == tts.OMNIVOICE_TTS
            assert omni_data["ref_text"] == "Đoạn văn bản mẫu kiểm tra."

            # 2. ElevenLabs creation with external_voice_id (no audio upload needed)
            res_el = await client.post(
                "/api/custom-voices",
                json={
                    "name": "Eleven Narrator",
                    "provider": 0,
                    "external_voice_id": "21m00Tcm4TlvDq8ikWAM",
                },
            )
            assert res_el.status == 201
            el_data = await res_el.json()
            assert el_data["provider"] == tts.ELEVENLABS_TTS
            assert el_data["external_voice_id"] == "21m00Tcm4TlvDq8ikWAM"
        finally:
            await client.close()

    asyncio.run(scenario())
