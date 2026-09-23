# -*- coding: utf-8 -*-
import asyncio
from aiohttp.test_utils import TestClient, TestServer
import pytest
from tests import webui_support as webui
from videotrans.core.db import init_db, set_db_path, get_db_path
from videotrans.core.project_store import create_project, get_project
from videotrans.core.job_store import create_job, append_event, mark_done


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    orig_path = get_db_path()
    test_db = tmp_path / "test_webui_projects.db"
    set_db_path(test_db)
    init_db()
    yield test_db
    set_db_path(orig_path)


@pytest.mark.asyncio
async def test_projects_crud_endpoints():
    app = webui.create_app()
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        # 1. Create project
        res_post = await client.post("/api/projects", json={
            "name": "My Dubbing Project",
            "duration": 45.0,
            "stage": 1,
            "status": "pending",
            "state": {"segments": [{"id": 1, "text": "intro"}]}
        })
        assert res_post.status == 201
        data = await res_post.json()
        pid = data["id"]
        assert data["name"] == "My Dubbing Project"
        assert data["state"]["segments"][0]["text"] == "intro"

        # 2. List projects
        res_list = await client.get("/api/projects")
        assert res_list.status == 200
        list_data = await res_list.json()
        assert len(list_data["projects"]) >= 1
        assert any(p["id"] == pid for p in list_data["projects"])

        # 3. Get project
        res_get = await client.get(f"/api/projects/{pid}")
        assert res_get.status == 200
        get_data = await res_get.json()
        assert get_data["id"] == pid

        # 4. Update project (Autosave)
        res_put = await client.put(f"/api/projects/{pid}", json={
            "stage": 2,
            "status": "completed",
            "state": {"segments": [{"id": 1, "text": "edited intro"}]}
        })
        assert res_put.status == 200
        put_data = await res_put.json()
        assert put_data["stage"] == 2
        assert put_data["status"] == "completed"
        assert put_data["state"]["segments"][0]["text"] == "edited intro"

        # 5. Resume project
        res_resume = await client.post(f"/api/projects/{pid}/resume")
        assert res_resume.status == 200
        resume_data = await res_resume.json()
        assert resume_data["ok"] is True
        assert resume_data["project"]["id"] == pid

        # 6. Delete project
        res_del = await client.delete(f"/api/projects/{pid}")
        assert res_del.status == 200
        del_data = await res_del.json()
        assert del_data["ok"] is True

        res_get_after = await client.get(f"/api/projects/{pid}")
        assert res_get_after.status == 404
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_job_sse_stream_replay():
    app = webui.create_app()
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        # Create a job with pre-existing sequenced events
        job_id = "job_sse_test_1"
        create_job(job_id, type="asr")
        append_event(job_id, {"status": "running", "progress": 25})
        append_event(job_id, {"status": "running", "progress": 75})
        mark_done(job_id)

        # Connect to stream with ?after_seq=1
        res = await client.get(f"/api/jobs/{job_id}/stream?after_seq=1")
        assert res.status == 200
        assert "text/event-stream" in res.headers.get("Content-Type", "")

        body = await res.text()
        assert "id: 2" in body
        assert "75" in body
        assert "event: done" in body
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_list_jobs_endpoint():
    app = webui.create_app()
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        create_project(project_id="proj_alpha", name="Project Alpha")
        create_project(project_id="proj_beta", name="Project Beta")

        create_job("job_p1_active", type="asr", project_id="proj_alpha")
        create_job("job_p1_done", type="render", project_id="proj_alpha")
        mark_done("job_p1_done")
        create_job("job_p2_active", type="asr", project_id="proj_beta")

        # 1. List all jobs
        res_all = await client.get("/api/jobs")
        assert res_all.status == 200
        all_jobs = (await res_all.json())["jobs"]
        assert len(all_jobs) >= 3

        # 2. Filter by project_id
        res_p1 = await client.get("/api/jobs?project_id=proj_alpha")
        assert res_p1.status == 200
        p1_jobs = (await res_p1.json())["jobs"]
        assert len(p1_jobs) == 2
        assert all(j["project_id"] == "proj_alpha" for j in p1_jobs)

        # 3. Filter by active status
        res_active = await client.get("/api/jobs?status=active")
        assert res_active.status == 200
        act_jobs = (await res_active.json())["jobs"]
        assert all(j["status"] in ("pending", "running") for j in act_jobs)
        assert any(j["id"] == "job_p1_active" for j in act_jobs)
        assert not any(j["id"] == "job_p1_done" for j in act_jobs)
    finally:
        await client.close()


def test_stage_artifact_directories_structure(tmp_path):
    from videotrans.core.project_store import init_project_dirs, get_project_dir
    pid = "test_dir_scaffold"
    dirs = init_project_dirs(pid)
    base = get_project_dir(pid)
    assert dirs["root"] == base
    assert dirs["media"].is_dir()
    assert dirs["transcripts"].is_dir()
    assert dirs["dubbing"].is_dir()
    assert dirs["exports"].is_dir()


def test_audio_hash_deduplication_lookup():
    from videotrans.core.content_hash import compute_content_hash
    from videotrans.core.project_store import find_project_by_audio_hash

    # Create dummy project with known hash
    dummy_hash = "abc123def456"
    create_project(
        project_id="proj_with_hash",
        name="Source Proj",
        audio_hash=dummy_hash,
        state={"segments": [{"id": 1, "text": "Cached text"}]},
        stage=2,
        status="completed",
    )

    found = find_project_by_audio_hash(dummy_hash)
    assert found is not None
    assert found["id"] == "proj_with_hash"
    assert found["state"]["segments"][0]["text"] == "Cached text"

