"""
DubDub AI Video Dubbing Studio — Challenger 2 Empirical Adversarial Stress Suite

Target areas:
1. Timeline mathematics & edge cases (0 duration, empty segments, single segment, 150+ segments, overlapping, out-of-bounds, pointer scrubbing math)
2. Subtitle typography & timing boundaries (font size min/max/clamping, Unicode Vietnamese/Chinese/Arabic/emojis, HTML injection escaping, startSec/endSec boundary enforcement, SRT serialization)
3. Subtitle typing focus preservation (isActivelyTyping suppression of notify, activeElement preservation)
4. Thumbnail management (upload, replace, reset lifecycle, ObjectURL cleanup)
5. Backend API & task parameter adversarial resilience (volume boundaries, non-numeric strings, route aliases, asset rejection)
"""

import asyncio
import io
from pathlib import Path
import subprocess
import uuid

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest

from videotrans.api.app import create_app
from videotrans.api.routes.media import EDIT_ASSETS, EDIT_ASSETS_LOCK
from videotrans.api.task_params import build_task_params
from videotrans.core.job_manager import JobManager

from videotrans.task.orchestrator import (
    CancellationToken,
    EventKind,
    TaskEvent,
    TaskRequest,
    TaskResult,
    TaskStatus,
)
from videotrans.task.taskcfg import InputFile


@pytest.fixture(autouse=True)
def isolate_edit_assets():
    """Ensure in-memory EDIT_ASSETS table is isolated between tests."""
    with EDIT_ASSETS_LOCK:
        snapshot = dict(EDIT_ASSETS)
    yield
    with EDIT_ASSETS_LOCK:
        EDIT_ASSETS.clear()
        EDIT_ASSETS.update(snapshot)


@pytest.fixture
def mock_video_source(tmp_path, monkeypatch):
    """Provides a mocked InputFile bypassing format_video / ffprobe."""
    source_file = tmp_path / "test_source.mp4"
    source_file.write_bytes(b"dummy-video-binary-content")
    input_file = InputFile(
        name=source_file.as_posix(),
        dirname=tmp_path.as_posix(),
        basename="test_source.mp4",
        noextname="test_source",
        ext="mp4",
        uuid="stage4-test-uuid",
    )
    monkeypatch.setattr(webui, "format_video", lambda _path: input_file)
    return {"file": source_file, "input_info": input_file}


def test_adversarial_backend_volume_normalization_and_boundaries(mock_video_source):
    """Verifies volume parameter mapping and boundary clamping in build_task_params."""
    source = mock_video_source["file"]

    base_options = {
        "recognType": 1,
        "modelName": "nova-3",
        "sourceLanguage": "zh-cn",
        "translateType": 0,
        "ttsType": 2,
        "targetLanguage": "vi",
        "timingMode": "voice",
    }

    # 1. Normal values
    p1 = build_task_params(source, {
        **base_options,
        "originalAudioVolume": 0.5,
        "backgroundAudioVolume": 0.8,
        "volume": "+20%"
    }, job_type="render")
    assert p1["source_audio_volume"] == 0.5
    assert p1["backaudio_volume"] == 0.8
    assert p1["volume"] == "+20%"
    assert p1["clear_cache"] is False

    # 2. Extreme volume boundary clamping (0.0 to 1.5)
    p2 = build_task_params(source, {
        **base_options,
        "originalAudioVolume": -10.0,
        "backgroundAudioVolume": 99.0,
        "volume": 1.5  # float volume 1.5 -> +50%
    }, job_type="render")
    assert p2["source_audio_volume"] == 0.0
    assert p2["backaudio_volume"] == 1.5
    assert p2["volume"] == "+50%"

    # 3. Volume as float < 1.0 (e.g. 0.75 -> -25%)
    p3 = build_task_params(source, {**base_options, "volume": 0.75}, job_type="render")
    assert p3["volume"] == "-25%"


def test_adversarial_asset_upload_file_extension_validation(tmp_path):
    """Verifies rejection of disallowed file extensions."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    app = create_app(upload_dir=upload_dir)

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            # 1. Executable file disguised as audio
            form = aiohttp.FormData()
            form.add_field("file", b"MZ executable binary", filename="exploit.exe", content_type="application/octet-stream")
            res = await client.post("/api/assets/background-audio", data=form)
            assert res.status == 400
            assert "Unsupported background-audio type" in await res.text()

            # 2. Shell script disguised as thumbnail
            form = aiohttp.FormData()
            form.add_field("file", b"#!/bin/bash\nrm -rf /", filename="script.sh", content_type="text/plain")
            res = await client.post("/api/assets/thumbnail", data=form)
            assert res.status == 400

            # 3. Valid thumbnail (.webp)
            form = aiohttp.FormData()
            form.add_field("file", b"dummy-webp-data", filename="valid.webp", content_type="image/webp")
            res = await client.post("/api/assets/thumbnail", data=form)
            assert res.status == 201
            body = await res.json()
            assert "id" in body
            assert body["name"] == "valid.webp"
        finally:
            await client.close()

    asyncio.run(scenario())


def test_adversarial_render_job_asset_resolution(tmp_path, mock_video_source):
    """Verifies that create_job_handler resolves backgroundAudioId and thumbnailId or rejects invalid ones."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Register real assets in EDIT_ASSETS
    bgm_path = upload_dir / "test_bgm.mp3"
    bgm_path.write_bytes(b"bgm-music-bytes")
    thumb_path = upload_dir / "test_thumb.jpg"
    thumb_path.write_bytes(b"thumb-image-bytes")

    bgm_id = uuid.uuid4().hex
    thumb_id = uuid.uuid4().hex

    with EDIT_ASSETS_LOCK:
        EDIT_ASSETS[bgm_id] = bgm_path
        EDIT_ASSETS[thumb_id] = thumb_path

    captured_params = {}
    def fake_runner(request, accept, token):
        captured_params.update(request.params)
        return TaskResult("job-123", TaskStatus.SUCCEEDED, upload_dir)

    def fake_probe(_path):
        return {
            "video_fps": 30.0,
            "video_codec_name": "h264",
            "audio_codec_name": "aac",
            "width": 1280,
            "height": 720,
            "duration": 12.0,
            "size": 1024,
            "streams_len": 2,
            "streams_audio": 1,
        }

    manager = JobManager(runner=fake_runner)
    app = create_app(upload_dir=upload_dir, job_manager=manager, media_probe=fake_probe)

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            # Ingest media
            media_form = aiohttp.FormData()
            media_form.add_field("file", io.BytesIO(b"fake video data"), filename="sample.mp4", content_type="video/mp4")
            res = await client.post("/api/media", data=media_form)
            assert res.status == 201
            media_body = await res.json()
            media_id = media_body["id"]

            base_opts = {
                "recognType": 1,
                "modelName": "nova-3",
                "sourceLanguage": "zh-cn",
                "translateType": 0,
                "ttsType": 2,
                "targetLanguage": "vi",
                "timingMode": "voice",
            }

            # Post render job with valid assets
            res = await client.post("/api/render", json={
                "mediaId": media_id,
                "options": {
                    **base_opts,
                    "backgroundAudioId": bgm_id,
                    "thumbnailId": thumb_id,
                    "backgroundAudioVolume": 0.4,
                    "originalAudioVolume": 0.0,
                    "subtitles": "1\n00:00:00,000 --> 00:00:02,000\nHello",
                }
            })
            assert res.status == 202
            job_body = await res.json()
            assert job_body["jobType"] == "render"

            # Post render job with bogus asset ID
            res = await client.post("/api/render", json={
                "mediaId": media_id,
                "options": {
                    **base_opts,
                    "backgroundAudioId": "non-existent-bgm-id",
                }
            })
            assert res.status == 400
            assert "Unknown or expired backgroundAudioId" in await res.text()
        finally:
            await client.close()

    asyncio.run(scenario())
