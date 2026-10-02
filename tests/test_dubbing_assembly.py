import wave

import pytest
from fastapi.testclient import TestClient

from videotrans.api.app import create_app
from videotrans.core import project_store, voice_store
from videotrans.core.db import get_db_path, init_db, set_db_path
from videotrans.core.project_store import create_project, get_project_dir
from videotrans.services.voice_preview import generate_fallback_preview_wav


@pytest.fixture
def project_with_previews(tmp_path, monkeypatch):
    previous_db = get_db_path()
    set_db_path(tmp_path / "projects.db")
    init_db()
    monkeypatch.setattr(project_store, "get_projects_root", lambda: tmp_path / "projects")
    monkeypatch.setattr(voice_store, "PREVIEWS_DIR", tmp_path / "previews")
    voice_store.init_voice_dirs()
    create_project(project_id="assembly-test", duration=3.0, stage=3)
    for suffix in ("aaaaaaaaaaaa", "bbbbbbbbbbbb"):
        generate_fallback_preview_wav(voice_store.get_preview_audio_path(f"prev_{suffix}.wav"), duration_sec=0.5)
    yield tmp_path
    set_db_path(previous_db)


def test_stage3_previews_are_stitched_for_stage4(project_with_previews):
    client = TestClient(create_app())
    response = client.post("/api/projects/assembly-test/dubbing/assemble", json={"segments": [
        {"id": 1, "startSec": 0.25, "endSec": 0.75, "targetText": "One", "previewAudioId": "prev_aaaaaaaaaaaa"},
        {"id": 2, "startSec": 1.5, "endSec": 2.0, "targetText": "Two", "previewAudioId": "prev_bbbbbbbbbbbb"},
    ]})
    assert response.status_code == 200, response.text
    audio_url = response.json()["audio_url"]
    audio = client.get(audio_url)
    assert audio.status_code == 200
    output = get_project_dir("assembly-test") / "dubbing" / "voiceover_merged.wav"
    with wave.open(str(output), "rb") as wav:
        assert wav.getnframes() / wav.getframerate() == pytest.approx(3.0, abs=0.03)
        wav.setpos(int(0.05 * wav.getframerate()))
        assert not any(wav.readframes(1000))
        wav.setpos(int(0.35 * wav.getframerate()))
        assert any(wav.readframes(1000))
        wav.setpos(int(1.1 * wav.getframerate()))
        assert not any(wav.readframes(1000))
        wav.setpos(int(1.6 * wav.getframerate()))
        assert any(wav.readframes(1000))


def test_stage4_handoff_rejects_missing_preview(project_with_previews):
    client = TestClient(create_app())
    response = client.post("/api/projects/assembly-test/dubbing/assemble", json={"segments": [
        {"id": 1, "startSec": 0, "endSec": 1, "targetText": "One"},
    ]})
    assert response.status_code == 400
    assert "segment 1" in response.json()["detail"]
    assert not (get_project_dir("assembly-test") / "dubbing" / "voiceover_merged.wav").exists()
