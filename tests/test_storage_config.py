# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
import pytest

from videotrans.core.db import init_db, set_db_path, db_conn
from videotrans.core import storage_config, project_store


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    test_db = tmp_path / "test_storage.db"
    set_db_path(test_db)
    init_db(test_db)
    yield


def test_validate_storage_path_rejects_empty_and_relative():
    ok, err = storage_config.validate_storage_path("output_dir", "")
    assert not ok
    assert "cannot be empty" in err

    ok, err = storage_config.validate_storage_path("output_dir", "relative/path")
    assert not ok
    assert "must be an absolute path" in err


def test_validate_storage_path_rejects_system_roots():
    sys_root = "C:\\" if sys.platform.startswith("win") else "/"
    ok, err = storage_config.validate_storage_path("output_dir", sys_root)
    assert not ok
    assert "protected system directory" in err


def test_validate_storage_path_rejects_collision(tmp_path):
    dir_a = tmp_path / "storage_a"
    dir_a.mkdir()

    other_paths = {"uploads_dir": str(dir_a)}
    ok, err = storage_config.validate_storage_path("output_dir", str(dir_a), other_paths)
    assert not ok
    assert "collides with" in err


def test_validate_storage_path_accepts_valid_writable_dir(tmp_path):
    valid_dir = tmp_path / "valid_output"
    ok, err = storage_config.validate_storage_path("output_dir", str(valid_dir))
    assert ok
    assert err == ""
    assert valid_dir.exists()


def test_storage_path_persistence_and_metrics(tmp_path):
    custom_out = tmp_path / "my_custom_output"
    custom_out.mkdir()
    (custom_out / "sample.txt").write_text("hello storage", encoding="utf-8")

    storage_config.set_storage_path("output_dir", str(custom_out))
    assert storage_config.get_storage_path("output_dir") == custom_out.resolve()

    metrics = storage_config.get_storage_metrics()
    assert "paths" in metrics
    assert "usage" in metrics
    assert metrics["paths"]["output_dir"] == str(custom_out.resolve())
    assert metrics["usage"]["output_dir_bytes"] > 0
    assert "disk_total_bytes" in metrics["usage"]


def test_clean_temp_cache_spares_active_jobs(tmp_path, monkeypatch):
    custom_temp = tmp_path / "temp"
    custom_temp.mkdir()
    monkeypatch.setattr(storage_config, "get_storage_path", lambda key: custom_temp if key == "temp_dir" else tmp_path / key)

    # Inactive/stale file
    stale_file = custom_temp / "stale_slice.wav"
    stale_file.write_text("junk audio")

    # Active job file
    active_job_id = "job-active-12345"
    with db_conn() as conn:
        conn.execute(
            "INSERT INTO jobs (id, type, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (active_job_id, "transcription", "running", 1000.0, 1000.0),
        )

    active_file = custom_temp / f"{active_job_id}_temp.wav"
    active_file.write_text("in-progress job audio")

    res = storage_config.clean_temp_cache()
    assert res["ok"] is True
    assert not stale_file.exists()
    assert active_file.exists()


def test_project_store_continuity_fallback(tmp_path, monkeypatch):
    legacy_root = tmp_path / "legacy_output" / "projects"
    legacy_pdir = legacy_root / "proj_legacy_001"
    legacy_pdir.mkdir(parents=True)
    (legacy_pdir / "project.json").write_text('{"name": "Legacy"}')

    custom_out = tmp_path / "new_output"
    custom_out.mkdir()

    monkeypatch.setattr(project_store, "DEFAULT_PROJECTS_DIR", legacy_root)
    monkeypatch.setattr(storage_config, "get_storage_path", lambda key: custom_out if key == "output_dir" else tmp_path / key)

    # Looking up legacy project should fall back to legacy directory
    found_dir = project_store.get_project_dir("proj_legacy_001")
    assert found_dir == legacy_pdir

    # New project should be created in new configured directory
    new_dir = project_store.get_project_dir("proj_brand_new_999")
    assert str(new_dir).startswith(str(custom_out))


def test_clean_temp_cache_protects_uploads_dir_nested_in_temp(tmp_path, monkeypatch):
    # Reproduces default layout where uploads_dir is inside temp_dir (ROOT_DIR/tmp/webui_uploads)
    custom_temp = tmp_path / "temp"
    custom_temp.mkdir()
    uploads_dir = custom_temp / "webui_uploads"
    uploads_dir.mkdir()

    user_video = uploads_dir / "user_uploaded_video.mp4"
    user_video.write_text("precious user video data")

    stale_scratch = custom_temp / "scratch.tmp"
    stale_scratch.write_text("throwaway cache")

    def mock_get_path(key):
        if key == "temp_dir":
            return custom_temp
        if key == "uploads_dir":
            return uploads_dir
        return tmp_path / key

    monkeypatch.setattr(storage_config, "get_storage_path", mock_get_path)

    res = storage_config.clean_temp_cache()
    assert res["ok"] is True
    # Scratch was cleaned
    assert not stale_scratch.exists()
    # Uploads directory and user uploaded video MUST remain intact!
    assert uploads_dir.exists()
    assert user_video.exists()
    assert user_video.read_text() == "precious user video data"


def test_validate_storage_path_rejects_application_root():
    from videotrans.configure._paths import ROOT_DIR
    ok, err = storage_config.validate_storage_path("temp_dir", ROOT_DIR)
    assert not ok
    assert "cannot be the application root" in err

