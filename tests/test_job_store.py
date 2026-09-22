# -*- coding: utf-8 -*-
import pytest
from videotrans.core.db import init_db, set_db_path, get_db_path
from videotrans.core.project_store import create_project
from videotrans.core.job_store import (
    create_job,
    get_job,
    list_jobs,
    mark_running,
    mark_done,
    mark_failed,
    mark_cancelled,
    append_event,
    events_since,
    sweep_orphans_on_startup,
)


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    orig_path = get_db_path()
    test_db = tmp_path / "test_jobs.db"
    set_db_path(test_db)
    init_db()
    yield test_db
    set_db_path(orig_path)


def test_job_lifecycle():
    proj = create_project(name="Proj For Job")
    job = create_job("job_101", type="asr", project_id=proj["id"], meta={"lang": "en"})
    assert job["id"] == "job_101"
    assert job["status"] == "pending"
    assert job["type"] == "asr"
    assert job["project_id"] == proj["id"]

    mark_running("job_101", stage="recogn", message="Transcribing...")
    j2 = get_job("job_101")
    assert j2["status"] == "running"
    assert j2["stage"] == "recogn"
    assert j2["message"] == "Transcribing..."

    mark_done("job_101", message="Transcribed 50 lines")
    j3 = get_job("job_101")
    assert j3["status"] == "succeeded"
    assert j3["progress"] == 100.0
    assert j3["finished_at"] is not None


def test_job_failed_and_cancelled():
    create_job("job_fail", type="render")
    mark_failed("job_fail", error="FFmpeg crashed")
    jf = get_job("job_fail")
    assert jf["status"] == "failed"
    assert jf["error"] == "FFmpeg crashed"

    create_job("job_cancel", type="translation")
    mark_cancelled("job_cancel", message="User aborted")
    jc = get_job("job_cancel")
    assert jc["status"] == "cancelled"
    assert jc["message"] == "User aborted"


def test_events_append_and_replay():
    create_job("job_events", type="asr")
    seq1 = append_event("job_events", {"kind": "running", "progress": 10})
    seq2 = append_event("job_events", {"kind": "progress", "progress": 50})
    seq3 = append_event("job_events", {"kind": "succeeded", "progress": 100})

    assert seq1 == 1
    assert seq2 == 2
    assert seq3 == 3

    all_events = events_since("job_events", after_seq=0)
    assert len(all_events) == 3
    assert all_events[0]["seq"] == 1

    partial = events_since("job_events", after_seq=1)
    assert len(partial) == 2
    assert partial[0]["seq"] == 2
    assert partial[1]["seq"] == 3


def test_event_capping():
    create_job("job_capped", type="stream")
    for i in range(520):
        append_event("job_capped", {"count": i})

    events = events_since("job_capped", after_seq=0, limit=1000)
    assert len(events) == 500
    assert events[0]["seq"] == 21
    assert events[-1]["seq"] == 520


def test_sweep_orphans_on_startup():
    create_job("job_orphan_1", type="asr")
    create_job("job_orphan_2", type="render")
    mark_running("job_orphan_2")
    create_job("job_done", type="trans")
    mark_done("job_done")

    swept = sweep_orphans_on_startup()
    assert swept == 2

    j1 = get_job("job_orphan_1")
    assert j1["status"] == "failed"
    assert "interrupted" in j1["error"].lower()

    j2 = get_job("job_orphan_2")
    assert j2["status"] == "failed"

    jd = get_job("job_done")
    assert jd["status"] == "succeeded"
