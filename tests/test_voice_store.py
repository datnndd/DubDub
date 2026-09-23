# -*- coding: utf-8 -*-
"""Unit tests for videotrans.core.voice_store."""
import json
from pathlib import Path
import pytest

from videotrans.core.db import init_db
from videotrans.core import voice_store
from videotrans import tts


@pytest.fixture
def temp_store(tmp_path, monkeypatch):
    """Set up an isolated database and storage folders."""
    db_path = tmp_path / "test_voices.db"
    init_db(db_path)

    v_dir = tmp_path / "data" / "voices"
    p_dir = tmp_path / "tmp" / "voice_previews"
    monkeypatch.setattr(voice_store, "VOICES_DIR", v_dir)
    monkeypatch.setattr(voice_store, "PREVIEWS_DIR", p_dir)
    voice_store.init_voice_dirs()

    return {"db_path": db_path, "v_dir": v_dir, "p_dir": p_dir}


def test_init_voice_dirs(temp_store):
    v_dir, p_dir = voice_store.init_voice_dirs()
    assert v_dir.is_dir()
    assert p_dir.is_dir()


def test_cwe22_path_protection(temp_store):
    v_dir = temp_store["v_dir"]

    # Valid relative filename
    resolved = voice_store.get_voice_audio_path("speaker1.wav")
    assert resolved == (v_dir / "speaker1.wav").resolve()

    # Empty filename
    with pytest.raises(ValueError, match="cannot be empty"):
        voice_store.get_voice_audio_path("")

    # Traversal attempt with ../
    with pytest.raises(ValueError, match="Path traversal"):
        voice_store.get_voice_audio_path("../../../etc/passwd")

    # Absolute path outside voices directory
    with pytest.raises(ValueError, match="Path traversal"):
        voice_store.get_voice_audio_path(Path("C:/Windows/System32/cmd.exe"))

    # Preview traversal
    with pytest.raises(ValueError, match="Path traversal"):
        voice_store.get_preview_audio_path("../../secret.key")


def test_voice_crud_lifecycle(temp_store):
    db_path = temp_store["db_path"]

    # Validation: empty name
    with pytest.raises(ValueError, match="Voice name cannot be empty"):
        voice_store.create_voice("   ", provider=tts.VIENEU_TTS, db_path=db_path)

    # 1. Create
    voice = voice_store.create_voice(
        name="Minh Thư",
        provider=tts.VIENEU_TTS,
        description="Warm Vietnamese narrator",
        language="vi",
        ref_audio_path="minh_thu.wav",
        tuning_params={"pace": 1.05, "timbreWarmth": 70},
        db_path=db_path,
    )
    assert voice["id"].startswith("voice_")
    assert voice["name"] == "Minh Thư"
    assert voice["provider"] == tts.VIENEU_TTS
    assert voice["language"] == "vi"
    assert voice["tuning_params"] == {"pace": 1.05, "timbreWarmth": 70}
    assert voice["is_active"] is True

    # 2. Get
    fetched = voice_store.get_voice(voice["id"], db_path=db_path)
    assert fetched is not None
    assert fetched["id"] == voice["id"]
    assert fetched["name"] == "Minh Thư"

    # Non-existent
    assert voice_store.get_voice("unknown_id", db_path=db_path) is None

    # 3. Find by name (case-insensitive)
    found = voice_store.find_voice_by_name("minh thư", provider=tts.VIENEU_TTS, db_path=db_path)
    assert found is not None
    assert found["id"] == voice["id"]

    # Wrong provider returns None
    assert voice_store.find_voice_by_name("minh thư", provider=tts.OMNIVOICE_TTS, db_path=db_path) is None

    # 4. List voices
    v_list = voice_store.list_voices(provider=tts.VIENEU_TTS, db_path=db_path)
    assert len(v_list) == 1
    assert v_list[0]["id"] == voice["id"]

    # 5. Update
    updated = voice_store.update_voice(
        voice["id"],
        name="Minh Thư (Official)",
        description="Updated description",
        tuning_params={"pace": 0.95},
        db_path=db_path,
    )
    assert updated["name"] == "Minh Thư (Official)"
    assert updated["description"] == "Updated description"
    assert updated["tuning_params"] == {"pace": 0.95}

    # Validation on update name
    with pytest.raises(ValueError, match="Voice name cannot be empty"):
        voice_store.update_voice(voice["id"], name="  ", db_path=db_path)

    # 6. Soft Delete
    assert voice_store.delete_voice(voice["id"], hard=False, db_path=db_path) is True
    # Should not be in active list
    assert len(voice_store.list_voices(provider=tts.VIENEU_TTS, active_only=True, db_path=db_path)) == 0
    # But still present in inactive list
    all_voices = voice_store.list_voices(provider=tts.VIENEU_TTS, active_only=False, db_path=db_path)
    assert len(all_voices) == 1
    assert all_voices[0]["is_active"] is False

    # 7. Hard Delete
    # Create fake audio files
    audio_file = temp_store["v_dir"] / "minh_thu.wav"
    audio_file.write_bytes(b"RIFFdummydata")
    preview_file = temp_store["p_dir"] / "minh_thu_preview.wav"
    preview_file.write_bytes(b"RIFFdummydata")

    voice_store.update_voice(
        voice["id"],
        preview_audio_path="minh_thu_preview.wav",
        db_path=db_path,
    )

    assert voice_store.delete_voice(voice["id"], hard=True, db_path=db_path) is True
    assert voice_store.get_voice(voice["id"], db_path=db_path) is None
    assert not audio_file.exists()
    assert not preview_file.exists()


def test_migrate_legacy_voices_idempotent(temp_store, monkeypatch):
    db_path = temp_store["db_path"]
    v_dir = temp_store["v_dir"]

    # Create dummy source files for legacy voices
    src_dir = temp_store["v_dir"].parent / "legacy_src"
    src_dir.mkdir(parents=True, exist_ok=True)

    vieneu_src = src_dir / "legacy_vn.wav"
    vieneu_src.write_bytes(b"RIFFlegacy_vn")

    f5_src = src_dir / "legacy_omni.wav"
    f5_src.write_bytes(b"RIFFlegacy_omni")

    mock_params = {
        "vieneu_roles": {
            "Legacy VieNeu Voice": str(vieneu_src),
        },
        "f5tts_role": f"{str(f5_src)}#Transcript for omnivoice reference audio",
    }
    monkeypatch.setattr("videotrans.configure.config.params", mock_params)

    # First migration run
    count1 = voice_store.migrate_legacy_voices(db_path=db_path)
    assert count1 == 2

    vn_voice = voice_store.find_voice_by_name("Legacy VieNeu Voice", provider=tts.VIENEU_TTS, db_path=db_path)
    assert vn_voice is not None
    assert vn_voice["provider"] == tts.VIENEU_TTS
    assert (v_dir / vn_voice["ref_audio_path"]).is_file()

    omni_voice = voice_store.find_voice_by_name("legacy_omni", provider=tts.OMNIVOICE_TTS, db_path=db_path)
    assert omni_voice is not None
    assert omni_voice["provider"] == tts.OMNIVOICE_TTS
    assert omni_voice["ref_text"] == "Transcript for omnivoice reference audio"
    assert (v_dir / omni_voice["ref_audio_path"]).is_file()

    # Second migration run: idempotent, migrates 0 additional
    count2 = voice_store.migrate_legacy_voices(db_path=db_path)
    assert count2 == 0


def test_omnivoice_and_vieneu_role_bridges(temp_store, monkeypatch):
    db_path = temp_store["db_path"]
    v_dir = temp_store["v_dir"]
    monkeypatch.setattr("videotrans.core.db._current_db_path", db_path)

    from videotrans.util import help_role

    # 1. Test VieNeu voice resolution variants
    vn_audio = v_dir / "vn_sample.wav"
    vn_audio.write_bytes(b"RIFFdummy_audio")

    vn_voice = voice_store.create_voice(
        name="Thùy Dương",
        provider=tts.VIENEU_TTS,
        voice_id="voice_vn1234",
        ref_audio_path="vn_sample.wav",
        db_path=db_path,
    )

    # Resolution by "Custom: {name}"
    path1 = help_role.get_vieneu_custom_voice_path("Custom: Thùy Dương")
    assert path1 == vn_audio.resolve().as_posix()

    # Resolution by bare name
    path2 = help_role.get_vieneu_custom_voice_path("Thùy Dương")
    assert path2 == vn_audio.resolve().as_posix()

    # Resolution by "Custom: {voice_id}"
    path3 = help_role.get_vieneu_custom_voice_path("Custom: voice_vn1234")
    assert path3 == vn_audio.resolve().as_posix()

    # Resolution by bare voice_id
    path4 = help_role.get_vieneu_custom_voice_path("voice_vn1234")
    assert path4 == vn_audio.resolve().as_posix()

    # 2. Test OmniVoice voice resolution and role_menu bridge
    omni_audio = v_dir / "omni_sample.wav"
    omni_audio.write_bytes(b"RIFFdummy_omni")

    omni_voice = voice_store.create_voice(
        name="Quốc Hùng",
        provider=tts.OMNIVOICE_TTS,
        voice_id="voice_omni5678",
        ref_audio_path="omni_sample.wav",
        ref_text="Xin chào các bạn đây là văn bản mẫu.",
        db_path=db_path,
    )

    # Resolution via get_omnivoice_voice_info by name
    w_path1, r_text1 = help_role.get_omnivoice_voice_info("Quốc Hùng")
    assert w_path1 == omni_audio.resolve().as_posix()
    assert r_text1 == "Xin chào các bạn đây là văn bản mẫu."

    # Resolution via get_omnivoice_voice_info by ID
    w_path2, r_text2 = help_role.get_omnivoice_voice_info("voice_omni5678")
    assert w_path2 == omni_audio.resolve().as_posix()
    assert r_text2 == "Xin chào các bạn đây là văn bản mẫu."

    # Verify get_f5tts_role includes custom voice
    f5_roles = help_role.get_f5tts_role()
    assert "Quốc Hùng" in f5_roles
    assert f5_roles["Quốc Hùng"]["ref_wav"] == omni_audio.resolve().as_posix()

    # Verify role_menu lists display name and excludes internal ID
    menu = help_role.role_menu(tts.OMNIVOICE_TTS)
    assert "Quốc Hùng" in menu
    assert "voice_omni5678" not in menu
