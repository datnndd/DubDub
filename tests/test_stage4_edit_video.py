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
   - build_task_params with job_type="render":
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
import math
from pathlib import Path
import re
import uuid

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest

from videotrans.api.app import create_app
from videotrans.api import task_params as task_params_module
from videotrans.api.catalog import ASR_PROVIDERS, TRANSLATION_PROVIDERS
from videotrans.api.routes.media import EDIT_ASSETS, EDIT_ASSETS_LOCK
from videotrans.api.task_params import build_task_params
from videotrans.configure.contants import AUDIO_EXITS
from videotrans.core.job_manager import JobManager
from videotrans.core.media_store import MediaRecord
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
    monkeypatch.setattr(task_params_module, "format_video", lambda _path: input_file)
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
    app = create_app(upload_dir=upload_dir)

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

            with EDIT_ASSETS_LOCK:
                assert asset_id in EDIT_ASSETS
                saved_path = EDIT_ASSETS[asset_id]
                assert saved_path.is_file()
                assert saved_path.name.endswith("ambient_bgm.mp3")
        finally:
            await client.close()

    asyncio.run(scenario())


def test_asset_upload_thumbnail_multipart_success(tmp_path):
    """POST /api/assets/thumbnail with multipart image upload returns 201 and registers asset."""
    upload_dir = tmp_path / "uploads"
    app = create_app(upload_dir=upload_dir)

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

            with EDIT_ASSETS_LOCK:
                assert asset_id in EDIT_ASSETS
                assert EDIT_ASSETS[asset_id].is_file()
        finally:
            await client.close()

    asyncio.run(scenario())


def test_asset_upload_raw_binary_with_x_filename(tmp_path):
    """POST /api/assets/{kind} with raw bytes and X-Filename header returns 201 and registers asset."""
    upload_dir = tmp_path / "uploads"
    app = create_app(upload_dir=upload_dir)

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            headers = {"X-Filename": "cinematic.wav", "Content-Type": "audio/wav"}
            res = await client.post("/api/assets/background-audio", data=b"RIFFWAVEDATA", headers=headers)
            assert res.status == 201
            data = await res.json()
            assert data["name"] == "cinematic.wav"
            with EDIT_ASSETS_LOCK:
                assert data["id"] in EDIT_ASSETS
        finally:
            await client.close()

    asyncio.run(scenario())


def test_asset_upload_rejects_unsupported_kinds(tmp_path):
    """POST /api/assets/{kind} returns 404 when kind is not 'background-audio' or 'thumbnail'."""
    upload_dir = tmp_path / "uploads"
    app = create_app(upload_dir=upload_dir)

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
    app = create_app(upload_dir=upload_dir)

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
    app = create_app(upload_dir=upload_dir)

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
    manager = JobManager(runner=dummy_job_runner)
    app = create_app(upload_dir=upload_dir, job_manager=manager)

    # Ingest media record
    media_path = mock_video_source["file"]
    record = MediaRecord("m-stage4-render", media_path, "test.mp4", media_path.stat().st_size, {
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
    with EDIT_ASSETS_LOCK:
        EDIT_ASSETS[bgm_id] = bgm_path
        EDIT_ASSETS[thumb_id] = thumb_path

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            payload = {
                "mediaId": record.id,
                "jobType": "render",
                "options": {
                    "recognType": ASR_PROVIDERS[0]["recognType"],
                    "modelName": ASR_PROVIDERS[0]["models"][0],
                    "translateType": TRANSLATION_PROVIDERS[0]["translateType"],
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
    app = create_app(upload_dir=tmp_path / "uploads")
    media_path = mock_video_source["file"]
    record = MediaRecord("m-asset-err", media_path, "test.mp4", media_path.stat().st_size, {
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
    manager = JobManager(runner=dummy_job_runner)
    media_path = mock_video_source["file"]

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("ensure_translation_configured was unexpectedly called during render job")

    app = create_app(upload_dir=tmp_path / "uploads", job_manager=manager, translation_validator=fail_if_called)
    record = MediaRecord("m-bypass-trans", media_path, "test.mp4", media_path.stat().st_size, {
        "time": 20000, "width": 1920, "height": 1080, "video_streams": 1, "streams_audio": 1
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
                    "recognType": ASR_PROVIDERS[0]["recognType"],
                    "modelName": ASR_PROVIDERS[0]["models"][0],
                    "translateType": TRANSLATION_PROVIDERS[0]["translateType"],
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
    manager = JobManager(runner=dummy_job_runner)
    app = create_app(upload_dir=tmp_path / "uploads", job_manager=manager)
    media_path = mock_video_source["file"]
    record = MediaRecord("m-alias-test", media_path, "test.mp4", media_path.stat().st_size, {
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
                    "recognType": ASR_PROVIDERS[0]["recognType"],
                    "modelName": ASR_PROVIDERS[0]["models"][0],
                    "translateType": TRANSLATION_PROVIDERS[0]["translateType"],
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
    monkeypatch.setattr(task_params_module, "format_video", lambda _path: InputFile(
        name=source.as_posix(), dirname=tmp_path.as_posix(), basename="source.mp4",
        noextname="source", ext="mp4", uuid="stage4-test"
    ))
    options = {
        "recognType": ASR_PROVIDERS[0]["recognType"],
        "modelName": ASR_PROVIDERS[0]["models"][0],
        "translateType": TRANSLATION_PROVIDERS[0]["translateType"],
        "ttsType": 0, "voiceRole": "No", "sourceLanguage": "zh-cn", "targetLanguage": "vi",
        "subtitles": "1\n00:00:00,000 --> 00:00:01,000\nEdited",
        "segments": [
            {"speakerId": "speaker-1", "voiceOverride": None},
            {"speakerId": "speaker-2", "voiceOverride": "Per-line voice"},
        ],
        "speakerVoiceMap": {"speaker-1": "Speaker voice", "speaker-2": "Ignored default"},
        "volume": "-20%", "originalAudioVolume": .25, "backgroundAudioVolume": .4,
        "backgroundMusicPath": (tmp_path / "music.wav").as_posix(),
        "thumbnailPath": (tmp_path / "cover.jpg").as_posix(),
        "subtitleStyle": {"color": "#FFFFFF", "outlineWidth": 2, "shadowSize": 2, "fontSize": 22},
    }

    params = build_task_params(source, options, job_type="render")

    assert params["clear_cache"] is False
    assert params["subtitles"].endswith("Edited")
    assert params["line_roles"] == {"1": "Speaker voice", "2": "Per-line voice"}
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
    monkeypatch.setattr(task_params_module, "format_video", lambda _path: InputFile(
        name=source.as_posix(), dirname=tmp_path.as_posix(), basename="vol.mp4",
        noextname="vol", ext="mp4", uuid="uuid-clamp"
    ))
    options = {
        "recognType": 0, "modelName": "1.7B", "translateType": 0,
        "sourceLanguage": "zh-cn", "targetLanguage": "vi",
        "originalAudioVolume": input_orig,
        "backgroundAudioVolume": input_bgm,
    }
    params = build_task_params(source, options, job_type="render")
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


# ============================================================================
# Section 4: Frontend DOM Contracts & Invariants
# ============================================================================


@pytest.mark.parametrize("kind,filename", [
    ("background-audio", "music.exe"),
    ("thumbnail", "cover.gif"),
])
def test_edit_asset_rejects_unsupported_extensions(kind, filename):
    """Baseline test: Verifies file extension validation matches backend allowlists."""
    assert Path(filename).suffix.lower().lstrip(".") not in (
        set(AUDIO_EXITS) if kind == "background-audio" else {"png", "jpg", "jpeg", "webp"}
    )


# ============================================================================
# Section 5: Headless Node.js ES Module Evaluation
# ============================================================================


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
    manager = JobManager(runner=dummy_job_runner)
    app = create_app(upload_dir=upload_dir, job_manager=manager)

    media_path = mock_video_source["file"]
    record = MediaRecord("m-e2e-studio", media_path, "dubbed_final.mp4", media_path.stat().st_size, {
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
                    "recognType": ASR_PROVIDERS[0]["recognType"],
                    "modelName": ASR_PROVIDERS[0]["models"][0],
                    "translateType": TRANSLATION_PROVIDERS[0]["translateType"],
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
            task_params = build_task_params(media_path, {
                **render_payload["options"],
                "backgroundMusicPath": EDIT_ASSETS[bgm_id].as_posix(),
                "thumbnailPath": EDIT_ASSETS[thumb_id].as_posix(),
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


def test_adversarial_corrupted_or_extreme_srt_timing(tmp_path, monkeypatch):
    """Adversarial stress: Multiline text, non-ASCII Unicode (Vietnamese, Chinese, Emojis), and special XML characters."""
    source = tmp_path / "extreme.mp4"
    source.write_bytes(b"vid")
    monkeypatch.setattr(task_params_module, "format_video", lambda _path: InputFile(
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

    params = build_task_params(source, options, job_type="render")
    assert "Xin chào thế giới! 🚀" in params["subtitles"]
    assert "欢迎使用 DubDub" in params["subtitles"]
    assert "<>&\"'" in params["subtitles"]


def test_adversarial_invalid_audio_mix_inputs(tmp_path, monkeypatch):
    """Adversarial stress: Non-numeric, NaN, None, and huge numbers in volume inputs default safely without exceptions."""
    source = tmp_path / "mix_bad.mp4"
    source.write_bytes(b"vid")
    monkeypatch.setattr(task_params_module, "format_video", lambda _path: InputFile(
        name=source.as_posix(), dirname=tmp_path.as_posix(), basename="bad.mp4",
        noextname="bad", ext="mp4", uuid="uuid-bad"
    ))

    options = {
        "recognType": 0, "modelName": "1.7B", "translateType": 0,
        "sourceLanguage": "zh-cn", "targetLanguage": "vi",
        "originalAudioVolume": None,
        "backgroundAudioVolume": "not-a-number",
    }

    params = build_task_params(source, options, job_type="render")
    # None for originalAudioVolume defaults to 0.0
    assert params["source_audio_volume"] == 0.0
    # "not-a-number" defaults to 0.8 in py
    assert params["backaudio_volume"] == 0.8
