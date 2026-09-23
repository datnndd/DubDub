"""
DubDub Stage 4 Adversarial Stress Test Suite
Covers backend endpoints, asset upload edge cases, audio volume mixing calculations,
and render export payload resilience.
"""

import asyncio
import math
from pathlib import Path
import uuid

import aiohttp
from aiohttp import web, FormData
from aiohttp.test_utils import TestClient, TestServer
import pytest

from videotrans.api.app import create_app
from videotrans.api.catalog import UPLOAD_DIR
from videotrans.api.routes.media import EDIT_ASSETS, EDIT_ASSETS_LOCK
from videotrans.api.task_params import build_task_params
from videotrans.configure.contants import AUDIO_EXITS, VIDEO_EXTS
from videotrans.core.media_store import MediaRecord
from videotrans.task.taskcfg import InputFile


# ============================================================================
# Test Fixtures & Doubles
# ============================================================================

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
    """Provides a mocked InputFile and bypasses format_video / ffprobe."""
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
    return {"file": source_file, "input_info": input_file}


def create_mock_media_record(app, media_id: str, media_path: Path):
    """Helper to inject a MediaRecord into the app's media store without running ffprobe."""
    record = MediaRecord(media_id, media_path, media_path.name, media_path.stat().st_size, {
        "time": 60000, "width": 1920, "height": 1080, "video_streams": 1, "streams_audio": 1
    })
    with app["media_store"]._lock:
        app["media_store"]._records[record.id] = record
    return record


# ============================================================================
# Area 1: Asset Upload Edge Cases
# ============================================================================

MALICIOUS_EXTENSIONS = [
    ".exe", ".sh", ".py", ".php", ".bin", ".tar.gz", ".bat", ".cmd", ".dll", ".js", ".html"
]

@pytest.mark.parametrize("bad_ext", MALICIOUS_EXTENSIONS)
def test_asset_upload_rejects_malicious_extensions(tmp_path, bad_ext):
    """POST /api/assets/{kind} must reject dangerous and malicious file extensions with HTTP 400."""
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            # 1. Background audio
            form = FormData()
            form.add_field("file", b"payload-bytes", filename=f"exploit{bad_ext}", content_type="application/octet-stream")
            res = await client.post("/api/assets/background-audio", data=form)
            assert res.status == 400, f"Expected 400 for audio exploit{bad_ext}, got {res.status}"
            err_text = await res.text()
            assert "Unsupported background-audio type" in err_text

            # 2. Thumbnail
            form = FormData()
            form.add_field("file", b"payload-bytes", filename=f"exploit{bad_ext}", content_type="application/octet-stream")
            res = await client.post("/api/assets/thumbnail", data=form)
            assert res.status == 400, f"Expected 400 for thumbnail exploit{bad_ext}, got {res.status}"
            err_text = await res.text()
            assert "Unsupported thumbnail type" in err_text
        finally:
            await client.close()

    asyncio.run(scenario())


PATH_TRAVERSAL_FILENAMES = [
    "../../test.png",
    "..\\..\\test.png",
    "/etc/passwd.png",
    "C:\\Windows\\System32\\test.png",
    "%2e%2e%2ftest.png",
    "....//....//test.png",
]

@pytest.mark.parametrize("traversal_name", PATH_TRAVERSAL_FILENAMES)
def test_asset_upload_path_traversal_sanitization(tmp_path, traversal_name):
    """
    POST /api/assets/thumbnail strips directory traversal vectors.
    Note: File is saved in UPLOAD_DIR, confirming that path traversal attempts
    do not escape the server's upload directory.
    """
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            form = FormData()
            form.add_field("file", b"\x89PNG\r\n\x1a\nsafe_data", filename=traversal_name, content_type="image/png")
            res = await client.post("/api/assets/thumbnail", data=form)
            assert res.status == 201
            data = await res.json()
            asset_id = data["id"]
            with EDIT_ASSETS_LOCK:
                saved_path = EDIT_ASSETS[asset_id]
                # Path traversal MUST NOT escape upload dir
                assert saved_path.parent.resolve() == app["media_store"].upload_dir.resolve()
                assert ".." not in saved_path.name
                assert "/" not in saved_path.name
                assert "\\" not in saved_path.name
        finally:
            await client.close()

    asyncio.run(scenario())


UNICODE_SPECIAL_FILENAMES = [
    "nhạc_nền_tiếng_việt_đặc_sắc.mp3",
    "背景音乐_中文_测试.mp3",
    "موسيقى_تصويرية.mp3",
    "BGM track with (spaces) & [symbols]!@#.mp3",
    "🎵_audio_sparkle.mp3",
]

@pytest.mark.parametrize("unicode_name", UNICODE_SPECIAL_FILENAMES)
def test_asset_upload_unicode_and_special_character_filenames(tmp_path, unicode_name):
    """POST /api/assets/background-audio preserves valid Unicode and special chars safely."""
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            form = FormData()
            form.add_field("file", b"ID3fake_mp3_content", filename=unicode_name, content_type="audio/mpeg")
            res = await client.post("/api/assets/background-audio", data=form)
            assert res.status == 201
            data = await res.json()
            assert "id" in data
            with EDIT_ASSETS_LOCK:
                saved_path = EDIT_ASSETS[data["id"]]
                assert saved_path.is_file()
                assert saved_path.parent.resolve() == app["media_store"].upload_dir.resolve()
        finally:
            await client.close()

    asyncio.run(scenario())


def test_asset_upload_empty_file_edge_case_behavior(tmp_path):
    """
    Stress test: empty (0 bytes) file uploads are safely rejected with HTTP 400.
    """
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            # 1. Raw binary with 0 bytes -> returns 400
            headers = {"X-Filename": "empty.mp3", "Content-Type": "audio/mpeg"}
            res_raw = await client.post("/api/assets/background-audio", data=b"", headers=headers)
            assert res_raw.status == 400

            # 2. Multipart with 0 bytes file -> rejected with 400
            form = FormData()
            form.add_field("file", b"", filename="empty.mp3", content_type="audio/mpeg")
            res_multi = await client.post("/api/assets/background-audio", data=form)
            assert res_multi.status == 400
        finally:
            await client.close()

    asyncio.run(scenario())


def test_asset_upload_missing_or_corrupt_headers(tmp_path):
    """POST /api/assets/background-audio with missing or corrupted headers."""
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            # Corrupted multipart boundary
            headers = {"Content-Type": "multipart/form-data; boundary=missing_boundary"}
            res = await client.post("/api/assets/background-audio", data=b"invalid-payload", headers=headers)
            assert res.status in {400, 500}

            # Missing file field in valid multipart
            form = FormData()
            form.add_field("wrong_field", b"audio_bytes", filename="audio.mp3")
            res = await client.post("/api/assets/background-audio", data=form)
            assert res.status == 400
        finally:
            await client.close()

    asyncio.run(scenario())


# ============================================================================
# Area 2: Audio Mix Parameter Math & Boundary Values
# ============================================================================

BASE_RENDER_OPTIONS = {
    "recognType": 0,
    "modelName": "1.7B",
    "translateType": 0,
    "ttsType": 0,
    "voiceRole": "No",
    "sourceLanguage": "zh-cn",
    "targetLanguage": "vi",
}

@pytest.mark.parametrize("raw_input,expected_norm", [
    (0.8, "-20%"),
    (1.25, "+25%"),
    (1.0, "+0%"),
    (0.0, "-100%"),
    (1.5, "+50%"),
    (2.0, "+100%"),
    ("-30%", "-30%"),
    ("+20%", "+20%"),
    ("40%", "+40%"),
    ("", "+0%"),
    (None, "+0%"),
    ("invalid_string", "invalid_string"),
])
def test_build_task_params_volume_normalization(mock_video_source, raw_input, expected_norm):
    """Test volume normalization across floats, percentages, and fallback values."""
    source = mock_video_source["file"]
    options = {
        **BASE_RENDER_OPTIONS,
        "volume": raw_input,
    }
    params = build_task_params(source, options, job_type="render")
    assert params["volume"] == expected_norm


@pytest.mark.parametrize("orig_in,expected_orig,bgm_in,expected_bgm", [
    (-50, 0.0, 200, 1.5),
    (0.0, 0.0, 1.5, 1.5),
    (0.75, 0.75, 0.35, 0.35),
    (-0.01, 0.0, 1.51, 1.5),
    (99999, 1.5, -99999, 0.0),
])
def test_build_task_params_volume_boundary_clamping_math(mock_video_source, orig_in, expected_orig, bgm_in, expected_bgm):
    """Clamps originalAudioVolume and backgroundAudioVolume strictly to [0.0, 1.5]."""
    source = mock_video_source["file"]
    options = {
        **BASE_RENDER_OPTIONS,
        "originalAudioVolume": orig_in,
        "backgroundAudioVolume": bgm_in,
    }
    params = build_task_params(source, options, job_type="render")
    assert math.isclose(params["source_audio_volume"], expected_orig, abs_tol=1e-5)
    assert math.isclose(params["backaudio_volume"], expected_bgm, abs_tol=1e-5)


def test_build_task_params_type_error_on_none_volumes(mock_video_source):
    """
    Stress test: Passing explicit None for volume values uses safe default without crashing.
    """
    source = mock_video_source["file"]
    options_orig_none = {
        **BASE_RENDER_OPTIONS,
        "originalAudioVolume": None,
    }
    params1 = build_task_params(source, options_orig_none, job_type="render")
    assert params1["source_audio_volume"] == 0.0

    options_bgm_none = {
        **BASE_RENDER_OPTIONS,
        "backgroundAudioVolume": None,
    }
    params2 = build_task_params(source, options_bgm_none, job_type="render")
    assert params2["backaudio_volume"] == 0.8


def test_build_task_params_overflow_on_infinite_volume(mock_video_source):
    """
    Stress test: Passing float('inf') is safely handled without unhandled OverflowError.
    """
    source = mock_video_source["file"]
    options_inf = {
        **BASE_RENDER_OPTIONS,
        "volume": float("inf"),
    }
    params = build_task_params(source, options_inf, job_type="render")
    assert params["volume"] in {"+0%", "+100%", "inf"}


# ============================================================================
# Area 3: Render Job Payload Verification
# ============================================================================

def test_create_render_job_rejects_non_existent_asset_id(tmp_path, mock_video_source):
    """Submitting render job with non-existent asset ID returns HTTP 400."""
    app = create_app(upload_dir=tmp_path / "uploads")
    media = create_mock_media_record(app, "m-s4-test-1", mock_video_source["file"])

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            payload = {
                "mediaId": media.id,
                "jobType": "render",
                "options": {
                    **BASE_RENDER_OPTIONS,
                    "backgroundAudioId": "non-existent-uuid-12345",
                }
            }
            res = await client.post("/api/render", json=payload)
            assert res.status == 400
            err = await res.text()
            assert "Unknown or expired backgroundAudioId" in err
        finally:
            await client.close()

    asyncio.run(scenario())


def test_create_render_job_rejects_expired_deleted_asset_file(tmp_path, mock_video_source):
    """Submitting render job with asset ID whose file was deleted from disk returns HTTP 400."""
    app = create_app(upload_dir=tmp_path / "uploads")
    media = create_mock_media_record(app, "m-s4-test-2", mock_video_source["file"])

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            deleted_file = tmp_path / "deleted_track.mp3"
            deleted_file.write_bytes(b"audio")
            asset_id = "expired-uuid-999"
            with EDIT_ASSETS_LOCK:
                EDIT_ASSETS[asset_id] = deleted_file
            # Delete file from disk to simulate expiration
            deleted_file.unlink()

            payload = {
                "mediaId": media.id,
                "jobType": "render",
                "options": {
                    **BASE_RENDER_OPTIONS,
                    "backgroundAudioId": asset_id,
                }
            }
            res = await client.post("/api/render", json=payload)
            assert res.status == 400
            err = await res.text()
            assert "Unknown or expired backgroundAudioId" in err
        finally:
            await client.close()

    asyncio.run(scenario())


def test_create_render_job_missing_options_or_media_id(tmp_path, mock_video_source):
    """POST /api/render and /api/export reject payloads with missing options or invalid mediaId."""
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            for route in ("/api/render", "/api/export"):
                # Missing options
                res = await client.post(route, json={"mediaId": "some-id"})
                assert res.status == 400
                assert "Job options are required" in (await res.text())

                # Missing mediaId
                res = await client.post(route, json={"options": {}})
                assert res.status == 400
                assert "Select and inspect a media file" in (await res.text())

                # Empty payload
                res = await client.post(route, json={})
                assert res.status == 400

                # Non-JSON payload
                res = await client.post(route, data="not-json")
                assert res.status == 400
                assert "A JSON job request is required" in (await res.text())
        finally:
            await client.close()

    asyncio.run(scenario())


def test_render_job_route_aliases_default_to_render_type(tmp_path, mock_video_source):
    """POST /api/render and POST /api/export default jobType to 'render'."""
    app = create_app(upload_dir=tmp_path / "uploads")
    media1 = create_mock_media_record(app, "m-s4-render-1", mock_video_source["file"])
    media2 = create_mock_media_record(app, "m-s4-export-2", mock_video_source["file"])

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            for route, media in (("/api/render", media1), ("/api/export", media2)):
                payload = {
                    "mediaId": media.id,
                    # Note: jobType omitted to test route-based defaulting
                    "options": {
                        **BASE_RENDER_OPTIONS,
                        "originalAudioVolume": 1.0,
                        "backgroundAudioVolume": 0.5,
                    }
                }
                res = await client.post(route, json=payload)
                assert res.status == 202
                job = await res.json()
                assert job["jobType"] == "render"

            # Adversarial test: Submitting while media has an active job returns 409 Conflict
            res_conflict = await client.post("/api/render", json={
                "mediaId": media1.id,
                "options": BASE_RENDER_OPTIONS,
            })
            assert res_conflict.status == 409
        finally:
            await client.close()

    asyncio.run(scenario())


def test_render_job_requires_asr_engine_unnecessarily(tmp_path, mock_video_source):
    """
    VULNERABILITY FINDING:
    When submitting /api/render without recognType in options,
    build_task_params raises ValueError: 'A valid ASR engine is required',
    Verified: When submitting /api/render without recognType in options,
    render job succeeds (HTTP 202) because render does not execute ASR.
    """
    app = create_app(upload_dir=tmp_path / "uploads")
    media = create_mock_media_record(app, "m-s4-test-4", mock_video_source["file"])

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            # Minimal render payload without ASR parameters
            payload = {
                "mediaId": media.id,
                "jobType": "render",
                "options": {
                    "subtitles": "1\\n00:00:00,000 --> 00:00:01,000\\nHello\\n",
                    "originalAudioVolume": 1.0,
                    "backgroundAudioVolume": 0.5,
                }
            }
            res = await client.post("/api/render", json=payload)
            assert res.status == 202
            job = await res.json()
            assert job["jobType"] == "render"
        finally:
            await client.close()

    asyncio.run(scenario())


# ============================================================================
# Area 4: Test Suite Import Verification
# ============================================================================

def test_verify_orchestrator_token_imports():
    """
    Verify CancellationToken, TaskRequest, TaskResult, TaskStatus are cleanly imported
    from 'videotrans.task.orchestrator'.
    """
    from videotrans.task.orchestrator import (
        CancellationToken,
        TaskRequest,
        TaskResult,
        TaskStatus,
    )
    assert CancellationToken is not None
    assert TaskRequest is not None
    assert TaskResult is not None
    assert TaskStatus is not None
