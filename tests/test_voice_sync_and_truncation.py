import math
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from videotrans.api.app import create_app
from videotrans.core import project_store, voice_store
from videotrans.core.db import get_db_path, init_db, set_db_path
from videotrans.core.project_store import create_project, get_project_dir
from videotrans.services.audio_fit import (
    FitParams,
    calculate_fit_rate,
    calculate_slot_duration,
    smart_fit_audio_file,
)
from videotrans.services.voice_preview import generate_fallback_preview_wav
from videotrans.task._rate import SpeedRate, TtsSpeedRate, _precise_speed_up_audio


@pytest.fixture
def sync_project(tmp_path, monkeypatch):
    previous_db = get_db_path()
    set_db_path(tmp_path / "projects.db")
    init_db()
    monkeypatch.setattr(project_store, "get_projects_root", lambda: tmp_path / "projects")
    monkeypatch.setattr(voice_store, "PREVIEWS_DIR", tmp_path / "previews")
    voice_store.init_voice_dirs()
    create_project(project_id="sync-test", duration=4.0, stage=3)
    yield tmp_path
    set_db_path(previous_db)


def _create_tone_wav(file_path: Path, duration_s: float, sample_rate: int = 48000, freq: float = 440.0):
    num_samples = int(duration_s * sample_rate)
    with wave.open(str(file_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        samples = bytearray()
        for i in range(num_samples):
            val = int(8000 * math.sin(2 * math.pi * freq * i / sample_rate))
            samples.extend(val.to_bytes(2, byteorder="little", signed=True))
        wf.writeframes(samples)


def test_slack_aware_assembly_does_not_truncate_speech_into_gap(sync_project):
    """
    Segment 1 has subtitle timing 0.2s - 0.6s (400ms duration).
    Its audio preview is 0.9s (900ms) long.
    Segment 2 starts at 1.8s.
    Under the old logic, clip was blindly sliced to 400ms, losing 500ms of speech.
    Under slack-aware bounding, the clip is allowed to finish into the gap (0.2 + 0.9 = 1.1s <= 1.8 - 0.03 = 1.77s).
    """
    prev1_path = voice_store.get_preview_audio_path("prev_111111111111.wav")
    prev2_path = voice_store.get_preview_audio_path("prev_222222222222.wav")
    _create_tone_wav(prev1_path, duration_s=0.9, freq=440.0)
    _create_tone_wav(prev2_path, duration_s=0.5, freq=880.0)

    client = TestClient(create_app())
    response = client.post("/api/projects/sync-test/dubbing/assemble", json={"segments": [
        {"id": 1, "startSec": 0.2, "endSec": 0.6, "targetText": "First sentence is longer", "previewAudioId": "prev_111111111111"},
        {"id": 2, "startSec": 1.8, "endSec": 2.3, "targetText": "Second sentence", "previewAudioId": "prev_222222222222"},
    ]})
    assert response.status_code == 200, response.text

    output = get_project_dir("sync-test") / "dubbing" / "voiceover_merged.wav"
    assert output.is_file()

    with wave.open(str(output), "rb") as wav:
        framerate = wav.getframerate()
        total_sec = wav.getnframes() / framerate
        assert total_sec == pytest.approx(4.0, abs=0.05)

        # At 0.8s (inside segment 1's trailing gap slack), audio MUST be audible!
        # With old logic (clipped at 0.6s), 0.8s was dead silence.
        wav.setpos(int(0.8 * framerate))
        frames_at_gap = wav.readframes(500)
        assert any(frames_at_gap), "Speech in trailing slack was prematurely cut off"

        # At 1.5s (before segment 2 starts at 1.8s), there should be silence (natural pause)
        wav.setpos(int(1.5 * framerate))
        frames_at_pause = wav.readframes(500)
        assert not any(frames_at_pause), "Inter-segment pause was not silent"

        # At 2.0s, segment 2 speech must be audible
        wav.setpos(int(2.0 * framerate))
        frames_seg2 = wav.readframes(500)
        assert any(frames_seg2), "Segment 2 speech was not audible"


def test_collision_guard_bounds_clip_with_fade_out(sync_project):
    """
    When speech overruns past the next segment's onset, it must be bounded
    at next_start - 30ms, preventing collision with the next speaker.
    """
    prev1_path = voice_store.get_preview_audio_path("prev_333333333333.wav")
    prev2_path = voice_store.get_preview_audio_path("prev_444444444444.wav")
    # Clip 1 is 2.0s long, starting at 0.0s. Segment 2 starts at 1.0s.
    # Without collision guard, clip 1 would bleed directly over segment 2.
    # With collision guard, clip 1 is bounded to 1.0 - 0.03 = 0.97s with a 30ms fade-out.
    _create_tone_wav(prev1_path, duration_s=2.0, freq=440.0)
    _create_tone_wav(prev2_path, duration_s=0.5, freq=880.0)

    client = TestClient(create_app())
    response = client.post("/api/projects/sync-test/dubbing/assemble", json={"segments": [
        {"id": 1, "startSec": 0.0, "endSec": 0.5, "targetText": "Very long utterance", "previewAudioId": "prev_333333333333"},
        {"id": 2, "startSec": 1.0, "endSec": 1.5, "targetText": "Next utterance", "previewAudioId": "prev_444444444444"},
    ]})
    assert response.status_code == 200, response.text

    output = get_project_dir("sync-test") / "dubbing" / "voiceover_merged.wav"
    with wave.open(str(output), "rb") as wav:
        framerate = wav.getframerate()
        # Right at 0.985s (in the 30ms safety buffer before 1.0s), sound should be attenuated / silent
        wav.setpos(int(0.985 * framerate))
        frames_guard = wav.readframes(int(0.01 * framerate))
        # Samples should be zero due to fade-out / cut at 0.97s
        assert not any(frames_guard), "Speech collided with next segment onset without 30ms guard"


def test_fit_params_defaults_and_slot_duration():
    params = FitParams()
    assert params.max_audio_rate == 1.35
    assert params.gap_guard_s == 0.15

    # calculate_slot_duration defaults to 0.15s gap guard
    slot = calculate_slot_duration(1.0, 3.0, next_start_s=4.0)
    # next_start (4.0) - gap_guard (0.15) = 3.85 effective end; 3.85 - 1.0 = 2.85s
    assert slot == pytest.approx(2.85, rel=1e-3)


def test_calculate_fit_rate_uses_135_cap():
    params = FitParams()
    # Need 1.30x speedup -> fits under 1.35x cap
    rate, status = calculate_fit_rate(2.6, 2.0, params)
    assert status == "audio_stretched"
    assert rate == pytest.approx(1.30, rel=1e-3)

    # Need 1.50x speedup -> capped at 1.35x max
    rate, status = calculate_fit_rate(3.0, 2.0, params)
    assert status == "overflow_trimmed"
    assert rate == 1.35


def test_smart_fit_removes_t_flag(tmp_path):
    input_wav = tmp_path / "fit_test_input.wav"
    output_wav = tmp_path / "fit_test_output.wav"
    _create_tone_wav(input_wav, duration_s=1.8)

    # Slot is 1.0s, natural duration is 1.8s. Need = 1.8x, capped at 1.35x.
    res_path, applied_rate, status = smart_fit_audio_file(
        input_wav,
        slot_duration_s=1.0,
        output_wav=output_wav,
    )
    assert status == "overflow_trimmed"
    assert applied_rate == 1.35
    assert res_path.is_file()

    # The output audio duration should be ~1.8s / 1.35 = ~1.33s (not truncated hard to 1.0s by -t)
    with wave.open(str(res_path), "rb") as wf:
        actual_dur = wf.getnframes() / wf.getframerate()
        assert actual_dur == pytest.approx(1.8 / 1.35, rel=0.08)


def test_speed_rate_and_tts_speed_rate_gap_and_limits(tmp_path):
    queue = [
        {"line": 1, "start_time": 0, "end_time": 1000, "filename": None},
        {"line": 2, "start_time": 3000, "end_time": 4000, "filename": None},
    ]

    rate = SpeedRate(
        queue_tts=queue,
        cache_folder=tmp_path.as_posix(),
        should_audiorate=True,
    )
    assert rate.max_audio_speed_rate <= 1.35

    rate._prepare_data()
    # Segment 1 end_time should absorb the gap up to next start (3000) - 150 = 2850ms
    assert queue[0]["end_time"] == 2850

    tts_queue = [
        {"line": 1, "start_time": 500, "end_time": 1500, "filename": None},
        {"line": 2, "start_time": 2500, "end_time": 3500, "filename": None},
    ]
    tts_rate = TtsSpeedRate(
        queue_tts=tts_queue,
        cache_folder=tmp_path.as_posix(),
        should_audiorate=True,
    )
    assert tts_rate.max_audio_speed_rate == 1.35

    tts_rate._prepare_data()
    # Segment 1 end_time should absorb up to 2500 - 150 = 2350ms
    assert tts_queue[0]["end_time"] == 2350


def test_precise_speed_up_audio_without_hard_t(tmp_path):
    in_wav = tmp_path / "in.wav"
    _create_tone_wav(in_wav, duration_s=1.0)
    # Speed up 1.0s audio to target duration 800ms
    success = _precise_speed_up_audio(input_path=str(in_wav), target_duration=800)
    assert success is True
    assert in_wav.is_file()
    with wave.open(str(in_wav), "rb") as wf:
        dur = wf.getnframes() / wf.getframerate()
        # Should be approximately 0.8s
        assert dur == pytest.approx(0.8, rel=0.08)


def test_zero_gap_and_overlapping_subtitles_bounded_with_collision_guard(sync_project):
    """
    On zero-gap (endSec == next_startSec) and overlapping subtitles (endSec > next_startSec),
    the earlier segment must be bounded at next_start - 30ms so that the 30ms collision guard
    is preserved and speech does not collide or overlap.
    """
    prev1_path = voice_store.get_preview_audio_path("prev_555555555555.wav")
    prev2_path = voice_store.get_preview_audio_path("prev_666666666666.wav")
    _create_tone_wav(prev1_path, duration_s=1.5, freq=440.0)
    _create_tone_wav(prev2_path, duration_s=0.5, freq=880.0)

    client = TestClient(create_app())
    response = client.post("/api/projects/sync-test/dubbing/assemble", json={"segments": [
        {"id": 1, "startSec": 0.0, "endSec": 1.2, "targetText": "Overlapping subtitle utterance", "previewAudioId": "prev_555555555555"},
        {"id": 2, "startSec": 1.0, "endSec": 1.5, "targetText": "Next utterance", "previewAudioId": "prev_666666666666"},
    ]})
    assert response.status_code == 200, response.text

    output = get_project_dir("sync-test") / "dubbing" / "voiceover_merged.wav"
    with wave.open(str(output), "rb") as wav:
        framerate = wav.getframerate()
        # At 0.985s (in 30ms guard), audio must be silent (bounded at 0.97s)
        wav.setpos(int(0.985 * framerate))
        frames_guard = wav.readframes(int(0.01 * framerate))
        assert not any(frames_guard), "Speech overlapped into next segment or violated 30ms guard"

        # At 1.1s, segment 2 audio must be audible
        wav.setpos(int(1.1 * framerate))
        frames_seg2 = wav.readframes(int(0.01 * framerate))
        assert any(frames_seg2), "Segment 2 speech was not audible"


def test_speed_rate_both_mode_clamps_audio_to_135(tmp_path):
    queue = [
        {"line": 1, "start_time": 0, "end_time": 1000, "filename": None, "source_duration": 1000, "dubb_time": 3000, "start_time_source": 0, "end_time_source": 1000},
    ]
    rate = SpeedRate(
        queue_tts=queue,
        cache_folder=tmp_path.as_posix(),
        should_audiorate=True,
        should_videorate=True,
    )
    rate._calculate_adjustments()
    assert len(rate.audio_data) == 1
    target_time = rate.audio_data[0]["target_time"]
    actual_rate = 3000 / target_time
    assert actual_rate <= 1.35


def test_unified_tts_preview_request_defaults_to_135():
    from videotrans.api.routes.voices import UnifiedTTSPreviewRequest
    req = UnifiedTTSPreviewRequest()
    assert req.max_speed_rate == 1.35


def test_stage_reset_preserves_135_max_speed(sync_project):
    from videotrans.core.stage_reset import reset_project_stage
    res = reset_project_stage("sync-test", 3)
    assert res["state"]["maxSpeedRate"] == 1.35

