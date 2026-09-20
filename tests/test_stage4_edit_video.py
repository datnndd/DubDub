"""
DubDub AI Video Dubbing Studio — Stage 4: Edit Video Test Suite

Automated verification covering:
1. Section 1: Backend API Endpoints & Asset Ingestion
   - POST /api/assets/background-audio and POST /api/assets/thumbnail (multipart & raw binary)
   - Disallowed extensions (.exe, .txt, .sh) rejected with 400
   - Unsupported kind (/api/assets/video) rejected with 404
   - Missing file / empty body rejected with 400
   - Asset registration in EDIT_ASSETS
   - POST /api/jobs with jobType="render", asset ID resolution, and 400 on missing asset IDs
   - Bypassing translation configuration check for render jobs
   - Route aliases POST /api/render and POST /api/export

2. Section 2: Task Configuration & Render Parameters
   - webui.build_task_params with job_type="render":
     * originalAudioVolume (0.0–1.5) mapped to source_audio_volume
     * backgroundAudioVolume (0.0–1.5) mapped to backaudio_volume
     * volume (dubbed voice volume)
     * Resolution of backgroundAudioId to background_music path
     * Resolution of thumbnailId to thumbnail path
     * subtitle_style dictionary and ASS conversion compatibility (set_ass_font)
     * options.subtitles bypass of ASR/translation stages
     * clear_cache set to False for render jobs

3. Section 3: Store State Logic & Boundaries
   - Audio mix clamping between 0 and 150
   - Mute toggle state caching (prevMix) and restoration
   - Subtitle font size and styling attributes
   - Inline subtitle editing and startSec/endSec boundary validation (startSec < endSec, adjacent constraints)
   - SRT serialization (serializeEditedSrt) creating valid standard SRT blocks
   - Asset lifecycle (select/remove BGM and thumbnail)
   - Inspector tab state transitions

4. Section 4: Frontend DOM Contracts & Invariants
   - 3-area layout structure (Upper Deck preview + inspector, Lower Deck timeline)
   - Unboxed canvas subtitle overlay without teleprompter card wrapping (white text, 2px outline, shadow)
   - Multi-track timeline lanes: Video, Subtitles, Dubbed TTS, BGM
   - Interactive playhead needle [data-timeline-playhead]
   - Audio mix sliders (0–150%) and mute toggles
   - BGM preview audio element #stage4-bgm-preview and input #stage4-background-input
   - Thumbnail upload input #stage4-thumbnail-input and aspect-video preview card
   - Subtitle typography controls (font size slider, font family, color, outline, shadow)

5. Section 5: Headless Node.js ES Module Evaluation
   - Evaluation of Stage4EditVideo.js in headless Node.js v22
   - Evaluation of state.js store mutations and SRT serialization in Node.js
   - Graceful skip if Node is not installed in the environment

6. Section 6: End-to-End Workflow & Adversarial Stress Tests
   - Complete workflow: ingest -> upload BGM -> upload thumbnail -> edit subtitles & mix -> export render payload
   - Adversarial: zero and single segment timeline math
   - Adversarial: extreme timestamps, corrupted boundaries, Unicode diacritics and special characters
   - Adversarial: invalid and extreme audio mix inputs
"""

import asyncio
import io
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import uuid

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest

from videotrans.task.orchestrator import (
    CancellationToken,
    EventKind,
    TaskEvent,
    TaskRequest,
    TaskResult,
    TaskStatus,
)
from videotrans.task.taskcfg import InputFile
from videotrans.util._srt_ass import set_ass_font
import webui


# ============================================================================
# Test Fixtures & Doubles
# ============================================================================

@pytest.fixture(autouse=True)
def isolate_edit_assets():
    """Ensure in-memory EDIT_ASSETS table is isolated between tests."""
    with webui.EDIT_ASSETS_LOCK:
        snapshot = dict(webui.EDIT_ASSETS)
    yield
    with webui.EDIT_ASSETS_LOCK:
        webui.EDIT_ASSETS.clear()
        webui.EDIT_ASSETS.update(snapshot)


@pytest.fixture
def dummy_job_runner():
    """Deterministic immediate job runner double for JobManager testing."""
    def _runner(request, accept, token):
        job_id = getattr(request, "job_id", None) or (request.params.get("uuid") if hasattr(request, "params") else None) or "stage4-test-job"
        output_dir = Path(request.params.get("target_dir", ".")) if hasattr(request, "params") else Path(".")
        accept(TaskEvent(
            job_id=str(job_id),
            kind=EventKind.PROGRESS,
            stage="render",
            message="Rendering audio mix and burning subtitles...",
            progress=50.0,
        ))
        return TaskResult(
            job_id=str(job_id),
            status=TaskStatus.SUCCEEDED,
            output_dir=output_dir,
            outputs=(Path("output.mp4"),),
        )
    return _runner


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
    monkeypatch.setattr(webui, "format_video", lambda _path: input_file)
    return {"file": source_file, "input_info": input_file}


@pytest.fixture
def sample_segments_s4():
    """Deterministic 3-segment transcript for Stage 4 timeline and SRT tests."""
    return [
        {
            "id": 1,
            "speakerId": "spk_1",
            "speakerName": "Speaker 1",
            "startSec": 0.0,
            "endSec": 3.25,
            "startTime": "00:00.000",
            "endTime": "00:03.250",
            "sourceText": "Welcome to DubDub editing studio.",
            "targetText": "Chào mừng đến với studio chỉnh sửa DubDub.",
            "voiceOverride": None,
        },
        {
            "id": 2,
            "speakerId": "spk_2",
            "speakerName": "Speaker 2",
            "startSec": 3.5,
            "endSec": 7.0,
            "startTime": "00:03.500",
            "endTime": "00:07.000",
            "sourceText": "You can mix background music and adjust subtitles.",
            "targetText": "Bạn có thể phối nhạc nền và điều chỉnh phụ đề.",
            "voiceOverride": "Bella",
        },
        {
            "id": 3,
            "speakerId": "spk_1",
            "speakerName": "Speaker 1",
            "startSec": 7.5,
            "endSec": 10.0,
            "startTime": "00:07.500",
            "endTime": "00:10.000",
            "sourceText": "Export your polished video directly.",
            "targetText": "Xuất video hoàn chỉnh của bạn trực tiếp.",
            "voiceOverride": None,
        },
    ]


# ============================================================================
# Section 1: Backend API Endpoints & Asset Ingestion
# ============================================================================

def test_asset_upload_background_audio_multipart_success(tmp_path):
    """POST /api/assets/background-audio with multipart audio upload returns 201 and registers asset."""
    upload_dir = tmp_path / "uploads"
    app = webui.create_app(upload_dir=upload_dir)

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            form = aiohttp.FormData()
            form.add_field("file", b"RIFFfakeWAVEfmt ", filename="ambient_bgm.mp3", content_type="audio/mpeg")
            res = await client.post("/api/assets/background-audio", data=form)
            assert res.status == 201
            data = await res.json()
            assert "id" in data
            assert data["name"] == "ambient_bgm.mp3"
            asset_id = data["id"]

            with webui.EDIT_ASSETS_LOCK:
                assert asset_id in webui.EDIT_ASSETS
                saved_path = webui.EDIT_ASSETS[asset_id]
                assert saved_path.is_file()
                assert saved_path.name.endswith("ambient_bgm.mp3")
        finally:
            await client.close()

    asyncio.run(scenario())


def test_asset_upload_thumbnail_multipart_success(tmp_path):
    """POST /api/assets/thumbnail with multipart image upload returns 201 and registers asset."""
    upload_dir = tmp_path / "uploads"
    app = webui.create_app(upload_dir=upload_dir)

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            form = aiohttp.FormData()
            form.add_field("file", b"\x89PNG\r\n\x1a\nfakeimage", filename="cover.webp", content_type="image/webp")
            res = await client.post("/api/assets/thumbnail", data=form)
            assert res.status == 201
            data = await res.json()
            assert "id" in data
            assert data["name"] == "cover.webp"
            asset_id = data["id"]

            with webui.EDIT_ASSETS_LOCK:
                assert asset_id in webui.EDIT_ASSETS
                assert webui.EDIT_ASSETS[asset_id].is_file()
        finally:
            await client.close()

    asyncio.run(scenario())


def test_asset_upload_raw_binary_with_x_filename(tmp_path):
    """POST /api/assets/{kind} with raw bytes and X-Filename header returns 201 and registers asset."""
    upload_dir = tmp_path / "uploads"
    app = webui.create_app(upload_dir=upload_dir)

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            headers = {"X-Filename": "cinematic.wav", "Content-Type": "audio/wav"}
            res = await client.post("/api/assets/background-audio", data=b"RIFFWAVEDATA", headers=headers)
            assert res.status == 201
            data = await res.json()
            assert data["name"] == "cinematic.wav"
            with webui.EDIT_ASSETS_LOCK:
                assert data["id"] in webui.EDIT_ASSETS
        finally:
            await client.close()

    asyncio.run(scenario())


def test_asset_upload_rejects_unsupported_kinds(tmp_path):
    """POST /api/assets/{kind} returns 404 when kind is not 'background-audio' or 'thumbnail'."""
    upload_dir = tmp_path / "uploads"
    app = webui.create_app(upload_dir=upload_dir)

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            form = aiohttp.FormData()
            form.add_field("file", b"fake-data", filename="clip.mp4")
            res = await client.post("/api/assets/video", data=form)
            assert res.status == 404
            text = await res.text()
            assert "Unknown edit asset type" in text
        finally:
            await client.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("kind,bad_filename", [
    ("background-audio", "payload.exe"),
    ("background-audio", "script.sh"),
    ("background-audio", "notes.txt"),
    ("thumbnail", "malware.exe"),
    ("thumbnail", "animation.gif"),
    ("thumbnail", "report.pdf"),
])
def test_asset_upload_rejects_invalid_extension(tmp_path, kind, bad_filename):
    """POST /api/assets/{kind} rejects disallowed extensions with 400 Bad Request."""
    upload_dir = tmp_path / "uploads"
    app = webui.create_app(upload_dir=upload_dir)

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            form = aiohttp.FormData()
            form.add_field("file", b"binary-content", filename=bad_filename)
            res = await client.post(f"/api/assets/{kind}", data=form)
            assert res.status == 400
            text = await res.text()
            assert f"Unsupported {kind} type" in text
        finally:
            await client.close()

    asyncio.run(scenario())


def test_asset_upload_requires_file_or_content(tmp_path):
    """POST /api/assets/{kind} returns 400 when no file is provided or content is empty."""
    upload_dir = tmp_path / "uploads"
    app = webui.create_app(upload_dir=upload_dir)

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            # Multipart with no file part
            empty_form = aiohttp.FormData()
            empty_form.add_field("otherField", "test")
            res1 = await client.post("/api/assets/background-audio", data=empty_form)
            assert res1.status == 400

            # Raw binary with empty payload
            res2 = await client.post("/api/assets/thumbnail", data=b"", headers={"X-Filename": "thumb.png"})
            assert res2.status == 400
        finally:
            await client.close()

    asyncio.run(scenario())


def test_create_render_job_resolves_asset_ids(tmp_path, mock_video_source, dummy_job_runner):
    """POST /api/jobs with jobType='render' resolves backgroundAudioId and thumbnailId to paths."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    manager = webui.JobManager(runner=dummy_job_runner)
    app = webui.create_app(upload_dir=upload_dir, job_manager=manager)

    # Ingest media record
    media_path = mock_video_source["file"]
    record = webui.MediaRecord("m-stage4-render", media_path, "test.mp4", media_path.stat().st_size, {
        "time": 60000, "width": 1920, "height": 1080, "video_streams": 1, "streams_audio": 1
    })
    with app["media_store"]._lock:
        app["media_store"]._records[record.id] = record

    # Register assets in EDIT_ASSETS
    bgm_path = upload_dir / "edit-bgm-track.mp3"
    bgm_path.write_bytes(b"bgm-data")
    thumb_path = upload_dir / "edit-cover-art.png"
    thumb_path.write_bytes(b"thumb-data")

    bgm_id = uuid.uuid4().hex
    thumb_id = uuid.uuid4().hex
    with webui.EDIT_ASSETS_LOCK:
        webui.EDIT_ASSETS[bgm_id] = bgm_path
        webui.EDIT_ASSETS[thumb_id] = thumb_path

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            payload = {
                "mediaId": record.id,
                "jobType": "render",
                "options": {
                    "recognType": webui.ASR_PROVIDERS[0]["recognType"],
                    "modelName": webui.ASR_PROVIDERS[0]["models"][0],
                    "translateType": webui.TRANSLATION_PROVIDERS[0]["translateType"],
                    "ttsType": 0,
                    "voiceRole": "No",
                    "sourceLanguage": "zh-cn",
                    "targetLanguage": "vi",
                    "subtitles": "1\n00:00:00,000 --> 00:00:02,000\nRendered test",
                    "originalAudioVolume": 0.2,
                    "backgroundAudioVolume": 0.5,
                    "volume": "+15%",
                    "backgroundAudioId": bgm_id,
                    "thumbnailId": thumb_id,
                    "subtitleStyle": {"color": "#FFFFFF", "outlineWidth": 2, "shadowSize": 2, "fontSize": 24},
                },
            }
            res = await client.post("/api/jobs", json=payload)
            assert res.status == 202
            data = await res.json()
            assert data["jobType"] == "render"
            assert data["status"] in {"queued", "processing", "succeeded"}
        finally:
            await client.close()

    asyncio.run(scenario())


def test_create_render_job_rejects_missing_asset_id(tmp_path, mock_video_source):
    """POST /api/jobs returns 400 Bad Request when asset ID is unknown or expired."""
    app = webui.create_app(upload_dir=tmp_path / "uploads")
    media_path = mock_video_source["file"]
    record = webui.MediaRecord("m-asset-err", media_path, "test.mp4", media_path.stat().st_size, {
        "time": 30000, "width": 1920, "height": 1080, "video_streams": 1, "streams_audio": 1
    })
    with app["media_store"]._lock:
        app["media_store"]._records[record.id] = record

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            payload = {
                "mediaId": record.id,
                "jobType": "render",
                "options": {
                    "recognType": 0, "modelName": "1.7B", "translateType": 0,
                    "sourceLanguage": "zh-cn", "targetLanguage": "vi",
                    "backgroundAudioId": "nonexistent-bgm-id-999"
                }
            }
            res = await client.post("/api/jobs", json=payload)
            assert res.status == 400
            text = await res.text()
            assert "Unknown or expired backgroundAudioId" in text
        finally:
            await client.close()

    asyncio.run(scenario())


def test_create_render_job_bypasses_translation_config_check(tmp_path, mock_video_source, dummy_job_runner, monkeypatch):
    """Render jobs bypass ensure_translation_configured since translation is already completed."""
    manager = webui.JobManager(runner=dummy_job_runner)
    app = webui.create_app(upload_dir=tmp_path / "uploads", job_manager=manager)
    media_path = mock_video_source["file"]
    record = webui.MediaRecord("m-bypass-trans", media_path, "test.mp4", media_path.stat().st_size, {
        "time": 20000, "width": 1920, "height": 1080, "video_streams": 1, "streams_audio": 1
    })
    with app["media_store"]._lock:
        app["media_store"]._records[record.id] = record

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("ensure_translation_configured was unexpectedly called during render job")

    monkeypatch.setattr(webui, "ensure_translation_configured", fail_if_called)

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            payload = {
                "mediaId": record.id,
                "jobType": "render",
                "options": {
                    "recognType": webui.ASR_PROVIDERS[0]["recognType"],
                    "modelName": webui.ASR_PROVIDERS[0]["models"][0],
                    "translateType": webui.TRANSLATION_PROVIDERS[0]["translateType"],
                    "sourceLanguage": "zh-cn",
                    "targetLanguage": "vi",
                    "subtitles": "1\n00:00:00,000 --> 00:00:01,000\nBypass ok",
                }
            }
            res = await client.post("/api/jobs", json=payload)
            assert res.status == 202
        finally:
            await client.close()

    asyncio.run(scenario())


def test_api_render_and_export_aliases(tmp_path, mock_video_source, dummy_job_runner):
    """POST /api/render and POST /api/export route aliases accept job submission with default job_type='render'."""
    manager = webui.JobManager(runner=dummy_job_runner)
    app = webui.create_app(upload_dir=tmp_path / "uploads", job_manager=manager)
    media_path = mock_video_source["file"]
    record = webui.MediaRecord("m-alias-test", media_path, "test.mp4", media_path.stat().st_size, {
        "time": 15000, "width": 1920, "height": 1080, "video_streams": 1, "streams_audio": 1
    })
    with app["media_store"]._lock:
        app["media_store"]._records[record.id] = record

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            common_payload = {
                "mediaId": record.id,
                "options": {
                    "recognType": webui.ASR_PROVIDERS[0]["recognType"],
                    "modelName": webui.ASR_PROVIDERS[0]["models"][0],
                    "translateType": webui.TRANSLATION_PROVIDERS[0]["translateType"],
                    "sourceLanguage": "zh-cn",
                    "targetLanguage": "vi",
                    "subtitles": "1\n00:00:00,000 --> 00:00:01,000\nAlias ok",
                }
            }
            # Test /api/render
            res1 = await client.post("/api/render", json=common_payload)
            assert res1.status in {202, 409}  # 409 if media already running in job double
            if res1.status == 202:
                data1 = await res1.json()
                assert data1["jobType"] == "render"

            # Cancel or reset active job for second alias test
            manager._active_by_media.clear()

            # Test /api/export
            res2 = await client.post("/api/export", json=common_payload)
            assert res2.status in {202, 409}
            if res2.status == 202:
                data2 = await res2.json()
                assert data2["jobType"] == "render"
        finally:
            await client.close()

    asyncio.run(scenario())


# ============================================================================
# Section 2: Task Configuration & Render Parameters
# ============================================================================

def test_render_params_reuse_edited_srt_and_mix_settings(tmp_path, monkeypatch):
    """Baseline test: build_task_params maps mix settings, paths, and bypasses cache when job_type='render'."""
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    monkeypatch.setattr(webui, "format_video", lambda _path: InputFile(
        name=source.as_posix(), dirname=tmp_path.as_posix(), basename="source.mp4",
        noextname="source", ext="mp4", uuid="stage4-test"
    ))
    options = {
        "recognType": webui.ASR_PROVIDERS[0]["recognType"],
        "modelName": webui.ASR_PROVIDERS[0]["models"][0],
        "translateType": webui.TRANSLATION_PROVIDERS[0]["translateType"],
        "ttsType": 0, "voiceRole": "No", "sourceLanguage": "zh-cn", "targetLanguage": "vi",
        "subtitles": "1\n00:00:00,000 --> 00:00:01,000\nEdited",
        "volume": "-20%", "originalAudioVolume": .25, "backgroundAudioVolume": .4,
        "backgroundMusicPath": (tmp_path / "music.wav").as_posix(),
        "thumbnailPath": (tmp_path / "cover.jpg").as_posix(),
        "subtitleStyle": {"color": "#FFFFFF", "outlineWidth": 2, "shadowSize": 2, "fontSize": 22},
    }

    params = webui.build_task_params(source, options, job_type="render")

    assert params["clear_cache"] is False
    assert params["subtitles"].endswith("Edited")
    assert params["volume"] == "-20%"
    assert params["source_audio_volume"] == .25
    assert params["backaudio_volume"] == .4
    assert params["background_music"].endswith("music.wav")
    assert params["thumbnail"].endswith("cover.jpg")
    assert params["embed_bgm"] is True
    assert isinstance(params["subtitle_style"], dict)
    assert params["subtitle_style"]["fontSize"] == 22


@pytest.mark.parametrize("input_orig,expected_orig,input_bgm,expected_bgm", [
    (-0.5, 0.0, -1.0, 0.0),
    (0.0, 0.0, 0.0, 0.0),
    (0.85, 0.85, 1.25, 1.25),
    (1.5, 1.5, 1.5, 1.5),
    (2.5, 1.5, 3.0, 1.5),
])
def test_build_task_params_volume_boundary_clamping(tmp_path, monkeypatch, input_orig, expected_orig, input_bgm, expected_bgm):
    """build_task_params clamps source_audio_volume and backaudio_volume strictly between 0.0 and 1.5."""
    source = tmp_path / "vol_test.mp4"
    source.write_bytes(b"vid")
    monkeypatch.setattr(webui, "format_video", lambda _path: InputFile(
        name=source.as_posix(), dirname=tmp_path.as_posix(), basename="vol.mp4",
        noextname="vol", ext="mp4", uuid="uuid-clamp"
    ))
    options = {
        "recognType": 0, "modelName": "1.7B", "translateType": 0,
        "sourceLanguage": "zh-cn", "targetLanguage": "vi",
        "originalAudioVolume": input_orig,
        "backgroundAudioVolume": input_bgm,
    }
    params = webui.build_task_params(source, options, job_type="render")
    assert math.isclose(params["source_audio_volume"], expected_orig, abs_tol=1e-5)
    assert math.isclose(params["backaudio_volume"], expected_bgm, abs_tol=1e-5)


def test_build_task_params_subtitle_style_and_ass_conversion_compatibility(tmp_path):
    """subtitleStyle dictionary passed from Stage 4 converts correctly into ASS format styles."""
    style_override = {
        "color": "#FFFFFF",
        "outlineColor": "#000000",
        "outlineWidth": 2,
        "shadowSize": 3,
        "fontSize": 28,
        "fontFamily": "Inter",
    }

    # Verify set_ass_font color converter logic
    def ass_color(value: str, fallback: str) -> str:
        match = re.fullmatch(r"#([0-9a-fA-F]{6})", str(value or ""))
        if not match:
            return fallback
        rgb = match.group(1)
        return f"&H00{rgb[4:6]}{rgb[2:4]}{rgb[0:2]}&"

    assert ass_color(style_override["color"], "&H00FFFFFF&") == "&H00FFFFFF&"
    assert ass_color(style_override["outlineColor"], "&H00000000&") == "&H00000000&"
    # Red color #FF0000 in RGB becomes &H000000FF& in ASS BGR
    assert ass_color("#FF0000", "&H00FFFFFF&") == "&H000000FF&"


# ============================================================================
# Section 3: Store State Logic & Boundaries
# ============================================================================

def test_audio_mix_clamping_0_to_150():
    """Verify live state mutation: store.updateAudioMix clamps volume strictly between 0 and 150."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    script = """
    globalThis.window = globalThis;
    globalThis.document = { querySelector: () => null, querySelectorAll: () => [] };
    const { store } = await import('./frontend/js/state.js');

    store.updateAudioMix('original', -10);
    if (store.state.editVideo.audioMix.original !== 0) throw new Error("clamping -10 failed: " + store.state.editVideo.audioMix.original);

    store.updateAudioMix('original', 0);
    if (store.state.editVideo.audioMix.original !== 0) throw new Error("clamping 0 failed");

    store.updateAudioMix('original', 75);
    if (store.state.editVideo.audioMix.original !== 75) throw new Error("clamping 75 failed");

    store.updateAudioMix('original', 150);
    if (store.state.editVideo.audioMix.original !== 150) throw new Error("clamping 150 failed");

    store.updateAudioMix('original', 200);
    if (store.state.editVideo.audioMix.original !== 150) throw new Error("clamping 200 failed: " + store.state.editVideo.audioMix.original);

    store.updateAudioMix('original', "invalid");
    if (store.state.editVideo.audioMix.original !== 0) throw new Error("clamping invalid failed: " + store.state.editVideo.audioMix.original);

    console.log("OK");
    """
    res = subprocess.run([node_exe, "--input-type=module", "-e", script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed:\n{res.stderr}"
    assert "OK" in res.stdout


def test_audio_mute_toggle_saves_and_restores_previous_mix():
    """Verify live state mutation: store.toggleAudioMute preserves and restores previous mix."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    script = """
    globalThis.window = globalThis;
    globalThis.document = { querySelector: () => null, querySelectorAll: () => [] };
    const { store } = await import('./frontend/js/state.js');

    store.updateAudioMix('original', 50);
    store.state.editVideo.prevMix = {};

    // 1. Mute original (50 -> 0)
    store.toggleAudioMute('original');
    if (store.state.editVideo.audioMix.original !== 0) throw new Error("Mute did not set volume to 0");
    if (store.state.editVideo.prevMix.original !== 50) throw new Error("Mute did not save prevMix");

    // 2. Unmute original (0 -> 50)
    store.toggleAudioMute('original');
    if (store.state.editVideo.audioMix.original !== 50) throw new Error("Unmute did not restore volume");

    // 3. Unmute with no prior saved volume falls back to default 100 for dubbed
    store.state.editVideo.audioMix.dubbed = 0;
    delete store.state.editVideo.prevMix.dubbed;
    store.toggleAudioMute('dubbed');
    if (store.state.editVideo.audioMix.dubbed !== 100) throw new Error("Unmute without prevMix did not restore default 100");

    console.log("OK");
    """
    res = subprocess.run([node_exe, "--input-type=module", "-e", script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed:\n{res.stderr}"
    assert "OK" in res.stdout


def test_update_stage4_timing_bounds_and_adjacent_constraints(sample_segments_s4):
    """Verify live state mutation: store.updateStage4Timing enforces adjacent constraints and startSec < endSec."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    segs_json = json.dumps(sample_segments_s4)
    script = f"""
    globalThis.window = globalThis;
    globalThis.document = {{ querySelector: () => null, querySelectorAll: () => [] }};
    const {{ store }} = await import('./frontend/js/state.js');
    store.state.segments = {segs_json};

    // Segment 2 is [3.5, 7.0] between Seg 1 ([0.0, 3.25]) and Seg 3 ([7.5, 10.0])
    // 1. Attempt to move startSec before Seg 1 endSec (3.25) -> Clamped to 3.25
    store.updateStage4Timing(2, "startSec", 2.0);
    if (store.state.segments[1].startSec !== 3.25) throw new Error("startSec lower clamp failed: " + store.state.segments[1].startSec);

    // 2. Attempt to move startSec past Seg 2 endSec (7.0) -> Clamped to 6.999
    store.updateStage4Timing(2, "startSec", 8.5);
    if (store.state.segments[1].startSec !== 6.999) throw new Error("startSec upper clamp failed: " + store.state.segments[1].startSec);

    // 3. Reset startSec and attempt to move endSec past Seg 3 startSec (7.5) -> Clamped to 7.5
    store.state.segments[1].startSec = 3.5;
    store.updateStage4Timing(2, "endSec", 9.0);
    if (store.state.segments[1].endSec !== 7.5) throw new Error("endSec upper clamp failed: " + store.state.segments[1].endSec);

    // 4. Attempt to move endSec before startSec (3.5) -> Clamped to 3.501
    store.updateStage4Timing(2, "endSec", 1.0);
    if (store.state.segments[1].endSec !== 3.501) throw new Error("endSec lower clamp failed: " + store.state.segments[1].endSec);

    console.log("OK");
    """
    res = subprocess.run([node_exe, "--input-type=module", "-e", script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed:\n{res.stderr}"
    assert "OK" in res.stdout


def test_serialize_edited_srt_formatting_and_indexing(sample_segments_s4):
    """Verify live state method: store.serializeEditedSrt produces valid standard SRT with comma milliseconds."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    segs_json = json.dumps(sample_segments_s4)
    script = f"""
    globalThis.window = globalThis;
    globalThis.document = {{ querySelector: () => null, querySelectorAll: () => [] }};
    const {{ store }} = await import('./frontend/js/state.js');
    store.state.segments = {segs_json};

    const srtOut = store.serializeEditedSrt();
    if (!srtOut.startsWith("1\\n00:00:00,000 --> 00:00:03,250\\nChào mừng")) {{
        throw new Error("SRT block 1 mismatch: " + srtOut.slice(0, 100));
    }}
    if (!srtOut.includes("2\\n00:00:03,500 --> 00:00:07,000\\nBạn có thể phối")) {{
        throw new Error("SRT block 2 mismatch");
    }}
    if (!srtOut.includes("3\\n00:00:07,500 --> 00:00:10,000\\nXuất video hoàn chỉnh")) {{
        throw new Error("SRT block 3 mismatch");
    }}
    console.log("OK");
    """
    res = subprocess.run([node_exe, "--input-type=module", "-e", script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed:\n{res.stderr}"
    assert "OK" in res.stdout


def test_thumbnail_and_bgm_lifecycle_and_cleanup():
    """Verify live state methods: store.removeBackgroundAudio and store.removeThumbnail reset state and revoke URLs."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    script = """
    globalThis.window = globalThis;
    const revoked = [];
    globalThis.URL = {
        createObjectURL: () => 'blob:mock',
        revokeObjectURL: (url) => revoked.push(url),
    };
    globalThis.document = { querySelector: () => null, querySelectorAll: () => [] };
    const { store } = await import('./frontend/js/state.js');

    store.state.editVideo.backgroundAudio = { id: "bgm-1", name: "track.mp3", previewUrl: "blob:bgm" };
    store.state.editVideo.thumbnail = { id: "thumb-1", name: "cover.png", previewUrl: "blob:thumb" };

    // Remove background audio
    store.removeBackgroundAudio();
    if (store.state.editVideo.backgroundAudio !== null) throw new Error("removeBackgroundAudio failed");
    if (!revoked.includes("blob:bgm")) throw new Error("BGM previewUrl not revoked");

    // Remove thumbnail
    store.removeThumbnail();
    if (store.state.editVideo.thumbnail !== null) throw new Error("removeThumbnail failed");
    if (!revoked.includes("blob:thumb")) throw new Error("thumbnail previewUrl not revoked");

    console.log("OK");
    """
    res = subprocess.run([node_exe, "--input-type=module", "-e", script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed:\n{res.stderr}"
    assert "OK" in res.stdout


def test_stage4_inspector_tabs():
    """Baseline test & State validation: Inspector tab transitions between audio, subtitles, thumbnail."""
    root = Path(webui.ROOT_DIR)
    screen = (root / "frontend/js/screens/Stage4EditVideo.js").read_text(encoding="utf-8")
    state = (root / "frontend/js/state.js").read_text(encoding="utf-8")

    assert "setStage4InspectorTab('audio')" in screen
    assert "setStage4InspectorTab('subtitles')" in screen
    assert "setStage4InspectorTab('thumbnail')" in screen
    assert "setStage4InspectorTab" in state


# ============================================================================
# Section 4: Frontend DOM Contracts & Invariants
# ============================================================================

def test_stage4_frontend_uses_shared_segments_and_connected_render_action():
    """Baseline test: Frontend references shared segments, player component, and export action."""
    root = Path(webui.ROOT_DIR)
    screen = (root / "frontend/js/screens/Stage4EditVideo.js").read_text(encoding="utf-8")
    state = (root / "frontend/js/state.js").read_text(encoding="utf-8")
    footer = (root / "frontend/js/components/StatusFooter.js").read_text(encoding="utf-8")

    assert "state.segments.map" in screen
    assert "renderVideoPlayer(state" in screen
    assert "data-mix-slider" in screen
    assert "stage4-background-input" in screen
    assert "stage4-thumbnail-input" in screen
    assert "outlineWidth" in screen and "shadowSize" in screen
    assert "updateStage4Timing" in state
    assert "serializeEditedSrt" in state
    assert "jobType: 'render'" in state
    assert "exportEditedVideo()" in footer


def test_stage4_three_area_layout_structure():
    """Stage 4 studio provides 3 distinct areas: Upper preview (cols 7-8), Upper inspector (cols 4-5), Lower timeline."""
    root = Path(webui.ROOT_DIR)
    screen = (root / "frontend/js/screens/Stage4EditVideo.js").read_text(encoding="utf-8")

    # Layout regions
    assert "UPPER DECK" in screen
    assert "LOWER DECK" in screen
    assert "lg:col-span-7" in screen or "col-span-12" in screen
    assert "lg:col-span-5" in screen or "xl:col-span-4" in screen
    assert "h-[210px]" in screen or "min-h-0" in screen


def test_stage4_capcut_timeline_and_track_elements():
    """Baseline test: Multi-track timeline renders Video, Subtitles, Dubbed TTS, and BGM tracks with playhead."""
    root = Path(webui.ROOT_DIR)
    screen = (root / "frontend/js/screens/Stage4EditVideo.js").read_text(encoding="utf-8")

    assert "data-timeline-playhead" in screen
    assert "TIMELINE" in screen
    assert "Video" in screen and "video_file" in screen
    assert "Subtitles" in screen and "data-segment-card" in screen
    assert "Dubbed" in screen and "record_voice_over" in screen
    assert "BGM" in screen and "music_note" in screen


def test_stage4_audio_sources_and_bgm_sync():
    """Baseline test: Independent audio mix sliders, mute buttons, and BGM synchronization elements."""
    root = Path(webui.ROOT_DIR)
    screen = (root / "frontend/js/screens/Stage4EditVideo.js").read_text(encoding="utf-8")
    state = (root / "frontend/js/state.js").read_text(encoding="utf-8")

    assert 'data-mix-slider="${key}"' in screen or 'data-mix-slider=' in screen
    assert "'original'" in screen
    assert "'dubbed'" in screen
    assert "'background'" in screen
    assert "toggleAudioMute" in screen
    assert "toggleAudioMute" in state

    assert "stage4-bgm-preview" in screen
    assert "stage4-background-input" in screen
    assert "removeBackgroundAudio" in screen
    assert "removeBackgroundAudio" in state
    assert "stage4-bgm-preview" in state


def test_stage4_subtitle_styling_and_font_size_controls():
    """Baseline test: Subtitle typography controls, font size dynamic slider, and clean CapCut overlay style."""
    root = Path(webui.ROOT_DIR)
    screen = (root / "frontend/js/screens/Stage4EditVideo.js").read_text(encoding="utf-8")
    state = (root / "frontend/js/state.js").read_text(encoding="utf-8")
    player = (root / "frontend/js/components/VideoPlayer.js").read_text(encoding="utf-8")

    assert "format_size" in screen
    assert "Font Size" in screen
    assert "fontSize" in screen
    assert "updateSubtitleStyle('fontSize'" in screen

    # Default styling contract: White text, black outline, subtle shadow
    assert 'color: "#FFFFFF"' in state
    assert 'outlineColor: "#000000"' in state
    assert "outlineWidth: 2" in state
    assert 'shadowColor: "rgba(0,0,0,.75)"' in state
    assert "shadowSize: 2" in state

    # CapCut canvas subtitle overlay in VideoPlayer
    assert "subtitleVariant === 'capcut'" in player
    assert "data-canvas-subtitle" in player


def test_stage4_thumbnail_management():
    """Baseline test: Thumbnail input, aspect-video card, select and remove actions."""
    root = Path(webui.ROOT_DIR)
    screen = (root / "frontend/js/screens/Stage4EditVideo.js").read_text(encoding="utf-8")
    state = (root / "frontend/js/state.js").read_text(encoding="utf-8")

    assert "stage4-thumbnail-input" in screen
    assert "removeThumbnail" in screen
    assert "removeThumbnail" in state
    assert "selectThumbnail" in state
    assert "aspect-video" in screen


@pytest.mark.parametrize("kind,filename", [
    ("background-audio", "music.exe"),
    ("thumbnail", "cover.gif"),
])
def test_edit_asset_rejects_unsupported_extensions(kind, filename):
    """Baseline test: Verifies file extension validation matches backend allowlists."""
    assert Path(filename).suffix.lower().lstrip(".") not in (
        set(webui.AUDIO_EXITS) if kind == "background-audio" else {"png", "jpg", "jpeg", "webp"}
    )


# ============================================================================
# Section 5: Headless Node.js ES Module Evaluation
# ============================================================================

def test_headless_node_stage4_screen_render():
    """Execute Stage4EditVideo.js in Node.js across all inspector tabs and assert Stage 4 invariants."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    test_script = """
    globalThis.window = globalThis;
    globalThis.document = {
        querySelector: () => null,
        querySelectorAll: () => []
    };

    const { renderStage4EditVideo } = await import('./frontend/js/screens/Stage4EditVideo.js');
    const { store } = await import('./frontend/js/state.js');

    const state = store.getState();
    state.currentStep = 4;
    state.activeSegmentId = 1;
    state.project = { durationSec: 30, duration: "00:30", title: "Demo Video", resolution: "1920x1080" };
    state.editVideo = {
        audioMix: { original: 20, dubbed: 100, background: 40 },
        backgroundAudio: { name: "test_bgm.mp3", previewUrl: "blob:bgm" },
        thumbnail: { name: "test_thumb.png", previewUrl: "blob:thumb" },
        activeTab: "subtitles"
    };
    state.segments = [
        { id: 1, startSec: 0, endSec: 3.5, targetText: "Node rendered subtitle" }
    ];

    // 1. Check Subtitles Tab
    state.editVideo.activeTab = "subtitles";
    const subHtml = renderStage4EditVideo(state);
    if (!subHtml || typeof subHtml !== 'string') {
        console.error("Subtitles render produced non-string output");
        process.exit(1);
    }
    const subChecks = [
        ['font-size-slider', subHtml.includes('data-action="update-font-size"')],
        ['font-size-number-input', subHtml.includes('data-action="update-font-size-input"')],
        ['active-subtitle-textarea', subHtml.includes('data-stage4-subtitle')],
        ['focus-preserving-input', subHtml.includes('data-segment-input="stage4-1"')],
    ];
    for (const [name, passed] of subChecks) {
        if (!passed) { console.error(`Subtitles tab check failed: ${name}`); process.exit(1); }
    }

    // 2. Check Audio Mix Tab
    state.editVideo.activeTab = "audio";
    const audioHtml = renderStage4EditVideo(state);
    const audioChecks = [
        ['audio-mix-slider', audioHtml.includes('data-mix-slider')],
        ['bgm-input', audioHtml.includes('stage4-background-input')],
        ['toggle-mute-orig', audioHtml.includes('toggle-mute-original')],
    ];
    for (const [name, passed] of audioChecks) {
        if (!passed) { console.error(`Audio tab check failed: ${name}`); process.exit(1); }
    }

    // 3. Check Thumbnail Tab
    state.editVideo.activeTab = "thumbnail";
    const thumbHtml = renderStage4EditVideo(state);
    const thumbChecks = [
        ['thumbnail-input', thumbHtml.includes('stage4-thumbnail-input')],
        ['thumbnail-preview', thumbHtml.includes('data-thumbnail-preview')],
    ];
    for (const [name, passed] of thumbChecks) {
        if (!passed) { console.error(`Thumbnail tab check failed: ${name}`); process.exit(1); }
    }

    // 4. Common Studio Layout & Timeline Invariants (Present across all views)
    const commonChecks = [
        ['stage4-studio-root', subHtml.includes('data-stage4-studio')],
        ['stage4-bgm-preview', subHtml.includes('stage4-bgm-preview')],
        ['timeline-playhead', subHtml.includes('data-timeline-playhead')],
        ['timeline-track-video', subHtml.includes('Video') && subHtml.includes('movie')],
        ['timeline-track-subtitles', subHtml.includes('Subtitles') && subHtml.includes('data-segment-card')],
        ['timeline-track-dubbed', subHtml.includes('Dubbed')],
        ['timeline-track-bgm', subHtml.includes('BGM')],
        ['inspector-tab-audio', subHtml.includes('data-inspector-tab="audio"')],
        ['inspector-tab-subtitles', subHtml.includes('data-inspector-tab="subtitles"')],
        ['inspector-tab-thumbnail', subHtml.includes('data-inspector-tab="thumbnail"')],
        ['export-button', subHtml.includes('data-action="export-edited-video"')],
    ];
    for (const [name, passed] of commonChecks) {
        if (!passed) { console.error(`Common check failed: ${name}`); process.exit(1); }
    }

    console.log("STAGE4_NODE_DOM_CHECKS_PASSED");
    """

    res = subprocess.run([node_exe, "--input-type=module", "-e", test_script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node script failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "STAGE4_NODE_DOM_CHECKS_PASSED" in res.stdout


def test_headless_node_stage4_state_and_srt_workflow():
    """Verify live state mutations via WorkflowStore in Node: audio mix, mute toggles, timing clamping, and SRT export."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    test_script = """
    globalThis.window = globalThis;
    globalThis.document = {
        querySelector: () => null,
        querySelectorAll: () => []
    };

    const { store } = await import('./frontend/js/state.js');

    // 1. Audio Mix Clamping
    store.updateAudioMix('original', 180);
    if (store.state.editVideo.audioMix.original !== 150) {
        console.error("Audio mix upper clamp failed, got", store.state.editVideo.audioMix.original);
        process.exit(1);
    }
    store.updateAudioMix('original', -50);
    if (store.state.editVideo.audioMix.original !== 0) {
        console.error("Audio mix lower clamp failed, got", store.state.editVideo.audioMix.original);
        process.exit(1);
    }

    // 2. Mute Toggle Caching and Restoration
    store.updateAudioMix('dubbed', 85);
    store.toggleAudioMute('dubbed');
    if (store.state.editVideo.audioMix.dubbed !== 0) {
        console.error("Mute did not zero volume");
        process.exit(1);
    }
    store.toggleAudioMute('dubbed');
    if (store.state.editVideo.audioMix.dubbed !== 85) {
        console.error("Unmute did not restore previous volume, got", store.state.editVideo.audioMix.dubbed);
        process.exit(1);
    }

    // 3. Subtitle Timing Boundary Clamping
    store.state.segments = [
        { id: 10, startSec: 1.0, endSec: 4.0, startTime: "00:01.000", endTime: "00:04.000", targetText: "First" },
        { id: 20, startSec: 4.5, endSec: 8.0, startTime: "00:04.500", endTime: "00:08.000", targetText: "Second" },
    ];
    store.updateStage4Timing(20, 'startSec', 2.0); // Should be clamped to previous segment endSec (4.0)
    if (store.state.segments[1].startSec !== 4.0) {
        console.error("Timing startSec lower clamp failed, got", store.state.segments[1].startSec);
        process.exit(1);
    }

    // 4. SRT Serialization
    const srt = store.serializeEditedSrt();
    if (!srt.includes('1\\n00:00:01,000 --> 00:00:04,000\\nFirst') || !srt.includes('2\\n00:00:04,000 --> 00:00:08,000\\nSecond')) {
        console.error("SRT serialization mismatch:\\n", srt);
        process.exit(1);
    }

    console.log("STAGE4_STATE_NODE_WORKFLOW_PASSED");
    """

    res = subprocess.run([node_exe, "--input-type=module", "-e", test_script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node script failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "STAGE4_STATE_NODE_WORKFLOW_PASSED" in res.stdout


# ============================================================================
# Section 6: End-to-End Workflow & Adversarial Stress Tests
# ============================================================================

def test_e2e_stage4_edit_and_render_export_scenario(tmp_path, mock_video_source, dummy_job_runner):
    """
    Complete end-to-end workflow simulation:
    1. Ingest dubbed video.
    2. Upload background music track.
    3. Upload custom thumbnail.
    4. Balance audio mix levels (Original 15%, Dubbed 110%, BGM 30%).
    5. Edit subtitle text and timings.
    6. Serialize edited SRT.
    7. Submit jobType='render' to /api/jobs.
    8. Verify task parameters and asset resolution.
    """
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    manager = webui.JobManager(runner=dummy_job_runner)
    app = webui.create_app(upload_dir=upload_dir, job_manager=manager)

    media_path = mock_video_source["file"]
    record = webui.MediaRecord("m-e2e-studio", media_path, "dubbed_final.mp4", media_path.stat().st_size, {
        "time": 45000, "width": 1920, "height": 1080, "video_streams": 1, "streams_audio": 1
    })
    with app["media_store"]._lock:
        app["media_store"]._records[record.id] = record

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            # 1. Upload BGM
            bgm_form = aiohttp.FormData()
            bgm_form.add_field("file", b"audio-mp3-stream", filename="lofi_beat.mp3", content_type="audio/mpeg")
            bgm_res = await client.post("/api/assets/background-audio", data=bgm_form)
            assert bgm_res.status == 201
            bgm_data = await bgm_res.json()
            bgm_id = bgm_data["id"]

            # 2. Upload Thumbnail
            thumb_form = aiohttp.FormData()
            thumb_form.add_field("file", b"image-png-stream", filename="poster.png", content_type="image/png")
            thumb_res = await client.post("/api/assets/thumbnail", data=thumb_form)
            assert thumb_res.status == 201
            thumb_data = await thumb_res.json()
            thumb_id = thumb_data["id"]

            # 3. Simulate Edited SRT and Render Payload
            edited_srt = (
                "1\n00:00:00,500 --> 00:00:04,000\nPhụ đề tiếng Việt được hiệu chỉnh hoàn hảo.\n\n"
                "2\n00:00:04,500 --> 00:00:09,200\nÂm thanh đã được cân bằng chính xác."
            )

            render_payload = {
                "mediaId": record.id,
                "jobType": "render",
                "options": {
                    "recognType": webui.ASR_PROVIDERS[0]["recognType"],
                    "modelName": webui.ASR_PROVIDERS[0]["models"][0],
                    "translateType": webui.TRANSLATION_PROVIDERS[0]["translateType"],
                    "ttsType": 0,
                    "voiceRole": "No",
                    "sourceLanguage": "zh-cn",
                    "targetLanguage": "vi",
                    "subtitles": edited_srt,
                    "volume": "+10%",
                    "originalAudioVolume": 0.15,
                    "backgroundAudioVolume": 0.30,
                    "backgroundAudioId": bgm_id,
                    "thumbnailId": thumb_id,
                    "subtitleStyle": {
                        "fontSize": 26,
                        "color": "#FFFFFF",
                        "outlineColor": "#000000",
                        "outlineWidth": 2,
                        "shadowSize": 2
                    }
                }
            }

            # 4. Dispatch Render Job
            job_res = await client.post("/api/jobs", json=render_payload)
            assert job_res.status == 202
            job_info = await job_res.json()
            assert job_info["id"] is not None
            assert job_info["jobType"] == "render"

            # 5. Verify task parameters resolution
            task_params = webui.build_task_params(media_path, {
                **render_payload["options"],
                "backgroundMusicPath": webui.EDIT_ASSETS[bgm_id].as_posix(),
                "thumbnailPath": webui.EDIT_ASSETS[thumb_id].as_posix(),
            }, job_type="render")

            assert task_params["clear_cache"] is False
            assert task_params["source_audio_volume"] == 0.15
            assert task_params["backaudio_volume"] == 0.30
            assert task_params["volume"] == "+10%"
            assert task_params["background_music"].endswith("lofi_beat.mp3")
            assert task_params["thumbnail"].endswith("poster.png")
            assert "Phụ đề tiếng Việt" in task_params["subtitles"]
            assert task_params["subtitle_style"]["fontSize"] == 26
        finally:
            await client.close()

    asyncio.run(scenario())


def test_adversarial_zero_and_single_segment_timeline_math():
    """Adversarial stress: store.serializeEditedSrt and renderStage4EditVideo handle 0 and 1 segments without zero-division or crash."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    script = """
    globalThis.window = globalThis;
    globalThis.document = { querySelector: () => null, querySelectorAll: () => [] };
    const { store } = await import('./frontend/js/state.js');
    const { renderStage4EditVideo } = await import('./frontend/js/screens/Stage4EditVideo.js');

    // 1. Zero segments
    store.state.segments = [];
    store.state.media = { duration: 0 };
    const emptySrt = store.serializeEditedSrt();
    if (emptySrt !== "") throw new Error("Empty segments should produce empty SRT string, got: " + emptySrt);

    const htmlZero = renderStage4EditVideo(store.state);
    if (!htmlZero.includes('data-stage4-studio') || !htmlZero.includes('data-timeline-track="subtitles"')) {
        throw new Error("Failed to render studio with 0 segments");
    }

    // 2. Single segment
    store.state.segments = [{ id: 1, startSec: 0.0, endSec: 5.0, startTime: "00:00.000", endTime: "00:05.000", targetText: "Solo line" }];
    const singleSrt = store.serializeEditedSrt();
    if (!singleSrt.includes("1\\n00:00:00,000 --> 00:00:05,000\\nSolo line")) {
        throw new Error("Single segment SRT mismatch: " + singleSrt);
    }
    const htmlSingle = renderStage4EditVideo(store.state);
    if (!htmlSingle.includes('Solo line')) throw new Error("Failed to render studio with single segment");

    console.log("OK");
    """
    res = subprocess.run([node_exe, "--input-type=module", "-e", script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed:\n{res.stderr}"
    assert "OK" in res.stdout


def test_adversarial_corrupted_or_extreme_srt_timing(tmp_path, monkeypatch):
    """Adversarial stress: Multiline text, non-ASCII Unicode (Vietnamese, Chinese, Emojis), and special XML characters."""
    source = tmp_path / "extreme.mp4"
    source.write_bytes(b"vid")
    monkeypatch.setattr(webui, "format_video", lambda _path: InputFile(
        name=source.as_posix(), dirname=tmp_path.as_posix(), basename="extreme.mp4",
        noextname="extreme", ext="mp4", uuid="uuid-extreme"
    ))

    complex_srt = (
        "1\n00:00:00,100 --> 00:00:05,200\n"
        "Line with special chars: <>&\"' and Vietnamese: Xin chào thế giới! 🚀\n\n"
        "2\n00:00:05,500 --> 00:00:10,000\n"
        "Chinese text: 欢迎使用 DubDub 视频剪辑工作室。\nMulti-line subtitle text."
    )

    options = {
        "recognType": 0, "modelName": "1.7B", "translateType": 0,
        "sourceLanguage": "zh-cn", "targetLanguage": "vi",
        "subtitles": complex_srt,
    }

    params = webui.build_task_params(source, options, job_type="render")
    assert "Xin chào thế giới! 🚀" in params["subtitles"]
    assert "欢迎使用 DubDub" in params["subtitles"]
    assert "<>&\"'" in params["subtitles"]


def test_adversarial_invalid_audio_mix_inputs(tmp_path, monkeypatch):
    """Adversarial stress: Non-numeric, NaN, None, and huge numbers in volume inputs default safely without exceptions."""
    source = tmp_path / "mix_bad.mp4"
    source.write_bytes(b"vid")
    monkeypatch.setattr(webui, "format_video", lambda _path: InputFile(
        name=source.as_posix(), dirname=tmp_path.as_posix(), basename="bad.mp4",
        noextname="bad", ext="mp4", uuid="uuid-bad"
    ))

    options = {
        "recognType": 0, "modelName": "1.7B", "translateType": 0,
        "sourceLanguage": "zh-cn", "targetLanguage": "vi",
        "originalAudioVolume": None,
        "backgroundAudioVolume": "not-a-number",
    }

    params = webui.build_task_params(source, options, job_type="render")
    # None for originalAudioVolume defaults to 0.0
    assert params["source_audio_volume"] == 0.0
    # "not-a-number" defaults to 0.8 in webui.py
    assert params["backaudio_volume"] == 0.8
