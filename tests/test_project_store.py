# -*- coding: utf-8 -*-
import pytest
from pathlib import Path
from videotrans.core.db import init_db, set_db_path, get_db_path
from videotrans.core.project_store import (
    create_project,
    get_project,
    list_projects,
    update_project,
    update_project_state,
    delete_project,
    find_project_by_audio_hash,
    get_project_dir,
)


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    orig_path = get_db_path()
    test_db = tmp_path / "test_projects.db"
    set_db_path(test_db)
    init_db()
    yield test_db
    set_db_path(orig_path)


def test_create_and_get_project():
    proj = create_project(
        name="Test Video Dub",
        media_id="media_123",
        duration=120.5,
        stage=1,
        status="pending",
        audio_hash="abc123hash",
        state={"segments": [{"id": 1, "text": "hello"}]},
    )
    assert proj["id"] is not None
    assert proj["name"] == "Test Video Dub"
    assert proj["media_id"] == "media_123"
    assert proj["duration"] == 120.5
    assert proj["stage"] == 1
    assert proj["status"] == "pending"
    assert proj["audio_hash"] == "abc123hash"
    assert proj["state"]["segments"][0]["text"] == "hello"

    fetched = get_project(proj["id"])
    assert fetched is not None
    assert fetched["id"] == proj["id"]
    assert fetched["name"] == "Test Video Dub"
    assert fetched["state"]["segments"][0]["text"] == "hello"


def test_update_project_state_and_stage():
    proj = create_project(name="Project Stage Flow")
    assert proj["stage"] == 1
    assert proj["status"] == "pending"

    updated = update_project_state(
        proj["id"],
        state_dict={"segments": [{"id": 1, "text": "translated"}]},
        stage=2,
        status="completed",
    )
    assert updated is not None
    assert updated["stage"] == 2
    assert updated["status"] == "completed"
    assert updated["state"]["segments"][0]["text"] == "translated"


def test_list_projects_order():
    p1 = create_project(name="Old Project")
    p2 = create_project(name="Newer Project")

    # Update p1 so it becomes newest
    update_project(p1["id"], name="Old Project Updated")

    projects = list_projects(limit=10)
    assert len(projects) >= 2
    assert projects[0]["id"] == p1["id"]
    assert projects[1]["id"] == p2["id"]


def test_find_project_by_audio_hash():
    proj = create_project(
        name="Audio Dub",
        audio_hash="unique_hash_987",
        state={"segments": [{"id": 1, "text": "cached"}]},
    )
    found = find_project_by_audio_hash("unique_hash_987")
    assert found is not None
    assert found["id"] == proj["id"]
    assert found["state"]["segments"][0]["text"] == "cached"

    assert find_project_by_audio_hash("nonexistent_hash") is None
    assert find_project_by_audio_hash("") is None


def test_delete_project_and_dirs():
    proj = create_project(name="To Delete")
    pdir = get_project_dir(proj["id"])
    assert pdir.exists()

    deleted = delete_project(proj["id"], delete_files=True)
    assert deleted is True
    assert get_project(proj["id"]) is None
    assert not pdir.exists()
