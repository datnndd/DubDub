import asyncio
import io
import threading
import time
from pathlib import Path

from aiohttp import FormData
from aiohttp.test_utils import TestClient, TestServer
import pytest

import webui
from videotrans import translator
from videotrans.task.orchestrator import EventKind, TaskEvent, TaskResult, TaskStatus


def test_new_frontend_is_the_only_webui():
    app = webui.create_app()
    routes = {route.resource.canonical for route in app.router.routes()}

    assert "/" in routes
    assert "/api/options" in routes
    assert "/api/media" in routes
    assert "/api/jobs" in routes
    assert "/api/jobs/{job_id}" in routes
    assert "gradio" not in Path(webui.__file__).read_text(encoding="utf-8").lower()


def test_build_task_params_maps_supported_frontend_fields(tmp_path, monkeypatch):
    source = tmp_path / "sample video.mp4"
    source.write_bytes(b"video")
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()
    monkeypatch.setattr(webui, "TEMP_DIR", str(temp_dir))
    monkeypatch.setattr(webui, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(webui, "role_menu", lambda *_args, **_kwargs: ["Voice A"])

    params = webui.build_task_params(source, {
        "sourceLanguage": "en",
        "targetLanguage": "fr",
        "recognType": 1,
        "translateType": 2,
        "ttsType": 3,
        "modelName": "test-model",
        "removeNoise": False,
        "speakerDiarization": True,
        "voiceRate": "+10%",
    })

    assert params["name"] == source.resolve().as_posix()
    assert params["source_language_code"] == "en"
    assert params["target_language_code"] == "fr"
    assert params["recogn_type"] == 1
    assert params["translate_type"] == 2
    assert params["tts_type"] == 3
    assert params["voice_role"] == "Voice A"
    assert params["remove_noise"] is False
    assert params["enable_diariz"] is True
    assert params["voice_rate"] == "+10%"
    assert Path(params["cache_folder"]).is_relative_to(temp_dir)


def test_build_task_params_rejects_unknown_backend_choices(tmp_path):
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"video")

    with pytest.raises(ValueError, match="ASR engine"):
        webui.build_task_params(source, {
            "sourceLanguage": next(iter(translator.LANGNAME_DICT)),
            "targetLanguage": next(iter(translator.LANGNAME_DICT)),
            "recognType": 9999,
            "translateType": 0,
            "ttsType": 0,
        })


def test_job_manager_reports_events_outputs_and_terminal_status(tmp_path, monkeypatch):
    output = tmp_path / "dubbed.mp4"
    output.write_bytes(b"result")

    def fake_run(_request, sink, _token):
        sink(TaskEvent("task", EventKind.RUNNING, "prepare"))
        sink(TaskEvent("task", EventKind.PROGRESS, "prepare", progress=42.0))
        return TaskResult("task", TaskStatus.SUCCEEDED, tmp_path, (output,))

    monkeypatch.setattr(webui, "run", fake_run)
    manager = webui.JobManager(runner=fake_run)
    job = manager.submit({"name": "unused"}, media_id="media")

    deadline = time.time() + 2
    while job.snapshot()["status"] not in {"succeeded", "failed", "cancelled"} and time.time() < deadline:
        time.sleep(0.01)
    snapshot = job.snapshot()

    assert snapshot["status"] == "succeeded"
    assert snapshot["stage"] == "prepare"
    assert snapshot["progress"] == 100.0
    assert snapshot["outputs"] == [{
        "name": "dubbed.mp4",
        "url": f"/api/jobs/{job.id}/outputs/0",
    }]


def test_cancel_is_scoped_to_one_job():
    manager = webui.JobManager()
    first = webui.JobRecord("first", webui.CancellationToken())
    second = webui.JobRecord("second", webui.CancellationToken())
    manager._jobs = {"first": first, "second": second}

    manager.cancel("first")

    assert first.token.is_cancelled()
    assert not second.token.is_cancelled()


def test_media_ingest_and_job_submission_are_end_to_end(tmp_path, monkeypatch):
    release = threading.Event()
    received = {}
    output = tmp_path / "dubbed.mp4"
    output.write_bytes(b"result")

    def fake_probe(path):
        assert Path(path).read_bytes() == b"synthetic video"
        return {
            "time": 12_345,
            "width": 1280,
            "height": 720,
            "video_fps": 25,
            "video_codec_name": "h264",
            "audio_codec_name": "aac",
            "format_name": "QuickTime / MOV",
            "bit_rate": 1_500_000,
            "audio_sample_rate": 48_000,
            "audio_channels": 2,
            "video_streams": 1,
            "streams_audio": 1,
        }

    def fake_run(request, sink, _token):
        received.update(request.params)
        sink(TaskEvent("task", EventKind.STAGE_STARTED, "prepare", message="Preparing media"))
        release.wait(2)
        return TaskResult("task", TaskStatus.SUCCEEDED, tmp_path, (output,))

    manager = webui.JobManager(runner=fake_run)
    monkeypatch.setattr(webui, "getset_gpu", lambda: None)
    app = webui.create_app(job_manager=manager, upload_dir=tmp_path / "uploads", media_probe=fake_probe)

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            form = FormData()
            form.add_field("file", io.BytesIO(b"synthetic video"), filename="sample clip.mp4", content_type="video/mp4")
            response = await client.post("/api/media", data=form)
            assert response.status == 201
            media = await response.json()
            assert media["filename"] == "sample clip.mp4"
            assert media["durationMs"] == 12_345
            assert media["sizeBytes"] == len(b"synthetic video")
            assert media["resolution"] == "1280x720"
            assert media["videoCodec"] == "h264"
            assert media["container"] == "QuickTime / MOV"
            assert media["bitrate"] == 1_500_000
            assert media["audioSampleRate"] == 48_000
            assert media["audioChannels"] == 2

            language_codes = list(translator.LANGNAME_DICT)
            payload = {
                "mediaId": media["id"],
                "options": {
                    "sourceLanguage": language_codes[0],
                    "targetLanguage": language_codes[-1],
                    "recognType": 0,
                    "translateType": 0,
                    "ttsType": 0,
                },
            }
            response = await client.post("/api/jobs", json=payload)
            assert response.status == 202
            job = await response.json()

            duplicate = await client.post("/api/jobs", json=payload)
            assert duplicate.status == 409
            assert "already running" in (await duplicate.text()).lower()

            release.set()
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                response = await client.get(f"/api/jobs/{job['id']}")
                snapshot = await response.json()
                if snapshot["status"] == "succeeded":
                    break
                await asyncio.sleep(0.01)
            assert snapshot["status"] == "succeeded"
            assert received["source_language_code"] == language_codes[0]
            assert received["target_language_code"] == language_codes[-1]
            assert received["name"].endswith("sample clip.mp4")
        finally:
            release.set()
            await client.close()

    asyncio.run(scenario())


def test_media_ingest_rejects_unreadable_media_and_removes_upload(tmp_path):
    def failed_probe(_path):
        raise ValueError("not readable media")

    upload_dir = tmp_path / "uploads"
    app = webui.create_app(upload_dir=upload_dir, media_probe=failed_probe)

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            form = FormData()
            form.add_field("file", io.BytesIO(b"broken"), filename="broken.mp4", content_type="video/mp4")
            response = await client.post("/api/media", data=form)
            assert response.status == 400
            assert "not readable media" in (await response.text()).lower()
            assert not list(upload_dir.glob("*"))
        finally:
            await client.close()

    asyncio.run(scenario())


def test_prepare_frontend_uses_ingested_media_and_real_disabled_state():
    state_source = (Path(webui.FRONTEND_DIR) / "js" / "state.js").read_text(encoding="utf-8")
    footer_source = (Path(webui.FRONTEND_DIR) / "js" / "components" / "StatusFooter.js").read_text(encoding="utf-8")

    assert "fetch('/api/media'" in state_source
    assert "mediaId" in state_source
    assert "disabled" in footer_source


def test_prepare_video_preview_has_sound_and_seek_controls():
    prepare_source = (Path(webui.FRONTEND_DIR) / "js" / "screens" / "Stage1Prepare.js").read_text(encoding="utf-8")
    state_source = (Path(webui.FRONTEND_DIR) / "js" / "state.js").read_text(encoding="utf-8")
    video_tag = prepare_source.split("<video data-source-preview", 1)[1].split(">", 1)[0]

    assert "controls" in video_tag
    assert "muted" not in video_tag
    assert 'type="range"' in prepare_source
    assert "seekPreview" in prepare_source
    assert "seekPreview" in state_source


def test_prepare_diagnostics_is_visible_at_tablet_and_desktop_widths():
    prepare_source = (Path(webui.FRONTEND_DIR) / "js" / "screens" / "Stage1Prepare.js").read_text(encoding="utf-8")

    assert 'col-span-12 md:col-span-7' in prepare_source
    assert 'col-span-12 md:col-span-5' in prepare_source
    assert "backend.error" in prepare_source
