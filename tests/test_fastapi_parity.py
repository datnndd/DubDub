# -*- coding: utf-8 -*-
import asyncio
import io
import json
from pathlib import Path

import httpx
import pytest

from videotrans.api.app import create_app
from videotrans.core.job_manager import JobManager, JobRecord
from videotrans.core.media_store import MediaRecord
from videotrans.task.orchestrator import TaskStatus


@pytest.mark.asyncio
async def test_sse_stream_returns_404_for_nonexistent_job(tmp_path):
    app = create_app(upload_dir=tmp_path / "uploads")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/jobs/nonexistent-job-id/stream")
        assert res.status_code == 404
        assert res.json() == {"detail": "Job not found"}


@pytest.mark.asyncio
async def test_sse_stream_headers_and_terminal_done_for_completed_job(tmp_path):
    manager = JobManager(runner=lambda *_: None)
    job = JobRecord("test-sse-job-1", {"name": "sample.mp4"}, job_type="render")
    job.status = "succeeded"
    manager._jobs[job.id] = job

    app = create_app(upload_dir=tmp_path / "uploads", job_manager=manager)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/jobs/{job.id}/stream")
        assert res.status_code == 200
        assert res.headers["cache-control"] == "no-cache, no-transform"
        assert res.headers.get("x-accel-buffering") == "no"
        assert "text/event-stream" in res.headers["content-type"]

        body = res.text
        assert "event: done" in body
        assert '"status": "succeeded"' in body
        assert '"terminal": true' in body


@pytest.mark.asyncio
async def test_sse_stream_live_completion_yields_done_event(tmp_path):
    manager = JobManager(runner=lambda *_: None)
    job = JobRecord("test-sse-job-live", {"name": "sample.mp4"}, job_type="render")
    job.status = "processing"
    manager._jobs[job.id] = job

    app = create_app(upload_dir=tmp_path / "uploads", job_manager=manager)

    async def complete_job_soon():
        await asyncio.sleep(0.05)
        job.update(status="succeeded", progress=100)

    asyncio.create_task(complete_job_soon())

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        async with client.stream("GET", f"/api/jobs/{job.id}/stream") as response:
            assert response.status_code == 200
            chunks = []
            async for chunk in response.aiter_text():
                chunks.append(chunk)
                if "event: done" in chunk:
                    break
            full_text = "".join(chunks)
            assert "event: done" in full_text
            assert '"status": "succeeded"' in full_text


@pytest.mark.asyncio
async def test_spa_redirect_dev_fallback_when_index_missing(tmp_path):
    empty_frontend = tmp_path / "frontend"
    empty_frontend.mkdir(parents=True, exist_ok=True)
    app = create_app(upload_dir=tmp_path / "uploads", frontend_dir=empty_frontend)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", follow_redirects=False) as client:
        res = await client.get("/")
        assert res.status_code == 307
        assert res.headers["location"] == "http://localhost:3000"


@pytest.mark.asyncio
async def test_spa_serves_index_html_with_no_cache_headers(tmp_path):
    fe_dir = tmp_path / "frontend" / "dist"
    fe_dir.mkdir(parents=True, exist_ok=True)
    index_file = fe_dir / "index.html"
    index_file.write_text("<!DOCTYPE html><html><head><title>pyVideoTrans</title></head><body><h1>App</h1></body></html>", encoding="utf-8")

    app = create_app(upload_dir=tmp_path / "uploads", frontend_dir=tmp_path / "frontend")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200
        assert "pyVideoTrans" in res.text
        assert "no-cache" in res.headers.get("cache-control", "")
        assert "no-store" in res.headers.get("cache-control", "")


@pytest.mark.asyncio
async def test_openapi_schema_contains_required_models(tmp_path):
    app = create_app(upload_dir=tmp_path / "uploads")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Check docs page
        docs_res = await client.get("/docs")
        assert docs_res.status_code == 200
        assert "swagger" in docs_res.text.lower()

        # Check OpenAPI json
        openapi_res = await client.get("/openapi.json")
        assert openapi_res.status_code == 200
        data = openapi_res.json()
        schemas = data["components"]["schemas"]
        for expected in [
            "JobCreateRequest",
            "ProjectCreateRequest",
            "ProjectUpdateRequest",
            "TranslationRequest",
            "OcrExtractRequest",
            "SegmentSplitRequest",
            "AsrSettingsRequest",
            "TranslationSettingsRequest",
        ]:
            assert expected in schemas, f"Missing {expected} in OpenAPI schemas"


@pytest.mark.asyncio
async def test_chunked_4mb_media_upload_stream(tmp_path):
    app = create_app(
        upload_dir=tmp_path / "uploads",
        media_probe=lambda p: {"time": 10.0, "width": 1920, "height": 1080},
    )
    # 5MB of dummy video data to exceed the 4MB chunk threshold
    five_mb = b"0" * (5 * 1024 * 1024)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/media",
            files={"file": ("large_test_video.mp4", io.BytesIO(five_mb), "video/mp4")},
        )
        assert res.status_code == 201
        body = res.json()
        assert body["id"]
        assert body["filename"] == "large_test_video.mp4"
        assert body["sizeBytes"] == len(five_mb)


@pytest.mark.asyncio
async def test_media_file_streaming_endpoint(tmp_path):
    app = create_app(
        upload_dir=tmp_path / "uploads",
        media_probe=lambda p: {"time": 1000.0, "width": 1280, "height": 720},
    )
    dummy_data = b"dummy video bytes"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Upload media
        upload_res = await client.post(
            "/api/media",
            files={"file": ("stream_test.mp4", io.BytesIO(dummy_data), "video/mp4")},
        )
        assert upload_res.status_code == 201
        media_id = upload_res.json()["id"]

        # 2. GET media file
        file_res = await client.get(f"/api/media/{media_id}/file")
        assert file_res.status_code == 200
        assert file_res.content == dummy_data

        # 3. GET nonexistent media
        bad_res = await client.get("/api/media/nonexistent-media-id/file")
        assert bad_res.status_code == 404


@pytest.mark.asyncio
async def test_project_update_and_artifact_persistence(tmp_path):
    app = create_app(upload_dir=tmp_path / "uploads")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create project
        create_res = await client.post(
            "/api/projects",
            json={"name": "Artifact Test Project", "stage": 1},
        )
        assert create_res.status_code == 201
        proj_id = create_res.json()["id"]

        # 2. Update with segments and stage 2
        segments_payload = [
          {
            "id": 1,
            "startSec": 0.5,
            "endSec": 2.5,
            "startTime": "00:00:00,500",
            "endTime": "00:00:02,500",
            "sourceText": "Hello persistent transcript",
            "targetText": "",
          }
        ]
        update_res = await client.put(
            f"/api/projects/{proj_id}",
            json={
                "stage": 2,
                "status": "completed",
                "state": {
                    "currentStep": 2,
                    "segments": segments_payload,
                    "transcript_options": {
                        "utterances": segments_payload,
                        "paragraphs": segments_payload,
                    },
                },
            },
        )
        assert update_res.status_code == 200
        data = update_res.json()
        assert data["stage"] == 2
        assert data["status"] == "completed"
        assert data["state"]["currentStep"] == 2
        assert len(data["state"]["segments"]) == 1

        # 3. Verify disk artifacts were written in project directory
        from videotrans.core.project_store import get_project_dir
        pdir = get_project_dir(proj_id)
        assert (pdir / "transcripts" / "segments.json").exists()
        assert (pdir / "transcripts" / "source.srt").exists()
        assert (pdir / "transcripts" / "transcript_options.json").exists()


@pytest.mark.asyncio
async def test_api_translate_production_handler(tmp_path):
    app = create_app(upload_dir=tmp_path / "uploads")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/translate",
            json={
                "sourceLanguage": "en",
                "targetLanguage": "en",
                "translateType": 0,
                "segments": [
                    {
                        "id": 1,
                        "sourceText": "Welcome to DubDub",
                        "startSec": 0.0,
                        "endSec": 2.0,
                    }
                ],
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert len(body["segments"]) == 1
        assert body["segments"][0]["targetText"] == "Welcome to DubDub"
        assert body["segments"][0]["id"] == 1


@pytest.mark.asyncio
async def test_project_media_persistence_and_server_restart_recovery(tmp_path):
    uploads = tmp_path / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    app = create_app(
        upload_dir=uploads,
        media_probe=lambda p: {"time": 5000.0, "width": 1920, "height": 1080, "video_streams": 1, "streams_audio": 1},
    )
    dummy_data = b"persisted video content for dubdub"

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Upload media
        upload_res = await client.post(
            "/api/media",
            files={"file": ("interview.mp4", io.BytesIO(dummy_data), "video/mp4")},
        )
        assert upload_res.status_code == 201
        media_id = upload_res.json()["id"]
        assert media_id

        # 2. Create an empty draft project
        create_res = await client.post("/api/projects", json={"name": "Persistent Project"})
        assert create_res.status_code == 201
        proj_id = create_res.json()["id"]

        # 3. Associate media with project via PUT /api/projects/{proj_id}
        update_res = await client.put(
            f"/api/projects/{proj_id}",
            json={
                "media_id": media_id,
                "state": {
                    "backend": {"mediaId": media_id},
                    "project": {"filename": "interview.mp4", "previewUrl": f"/api/media/{media_id}/file"},
                },
            },
        )
        assert update_res.status_code == 200
        updated = update_res.json()
        assert updated["media_id"] == media_id
        assert updated["media_path"]
        assert Path(updated["media_path"]).is_file()

        # 4. Fetch project via GET
        get_res = await client.get(f"/api/projects/{proj_id}")
        assert get_res.status_code == 200
        proj_data = get_res.json()
        assert proj_data["media_id"] == media_id

        # 5. Simulate backend server restart by clearing in-memory records
        app.state.media_store._records.clear()
        assert media_id not in app.state.media_store._records

        # 6. Verify self-healing lookup restores media and serves file
        file_res = await client.get(f"/api/media/{media_id}/file")
        assert file_res.status_code == 200
        assert file_res.content == dummy_data

        # 7. Record is now rehydrated in memory
        assert media_id in app.state.media_store._records


