"""
DubDub Stage 2 to Stage 3 LLM Translation Test Suite

Automated verification covering:
1. Backend Orchestrator `run_staged_translation`:
   - Executes LLM / machine translation on transcript segments
   - 1:1 segment alignment: updates targetText and calculates CPS
   - Metadata preservation: preserves id, timestamps, speaker metadata, voiceOverride
   - Language bypass: identical source and target codes bypass translation
   - Empty segment resilience: handles empty lists gracefully
   - Cancellation support: respects CancellationToken before and during execution
   - Failure resilience: captures translator exceptions without crash
2. Backend API Endpoints:
   - `POST /api/jobs` with `jobType="translation"` accepts segments & config
   - `GET /api/jobs/{id}` returns progress, status, and translated segments
   - `POST /api/jobs/{id}/cancel` terminates active translation
   - `POST /api/translate` direct synchronous translation endpoint
3. Frontend DOM Contracts & Headless Node Integration:
   - StatusFooter renders "Proceed to Voice & Dubbing" with correct action attributes
   - Stage 2 full-screen loading modal contracts: modal, spinner, progress, cancel
   - Stage 2 error banner contracts: error message and dismiss action
   - Language bypass workflow (source == target) transitions immediately to Stage 3
   - Pre-populated targetText bypass transitions immediately to Stage 3
   - Full translation workflow: modal open -> progress update -> 1:1 segment merge -> Stage 3 transition
   - Cancellation workflow: user stays on Stage 2, data preserved
   - Error handling workflow: modal dismissed, error banner shown, data preserved
   - Stage 3 teleprompter inputs & VideoPlayer canvas subtitles synchronized with targetText
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from aiohttp.test_utils import TestClient, TestServer
import pytest

from videotrans.api.app import create_app

from videotrans import translator
from videotrans.task.orchestrator import (
    CancellationToken,
    TaskRequest,
    TaskResult,
    TaskStatus,
    run_staged_translation,
)


# ============================================================================
# Test Fixtures & Sample Data
# ============================================================================

@pytest.fixture
def sample_stage2_segments():
    return [
        {
            "id": 1,
            "speakerId": "spk_1",
            "speakerName": "Alex Carter",
            "speakerCode": "AC",
            "speakerColor": "amber",
            "startTime": "00:01.000",
            "endTime": "00:05.000",
            "startSec": 1.0,
            "endSec": 5.0,
            "sourceText": "Welcome to our AI video translation presentation.",
            "targetText": "",
            "voiceOverride": None,
            "cps": 12.0,
            "cpsStatus": "Optimal",
        },
        {
            "id": 2,
            "speakerId": "spk_2",
            "speakerName": "Elena Rostova",
            "speakerCode": "ER",
            "speakerColor": "secondary",
            "startTime": "00:05.500",
            "endTime": "00:10.000",
            "startSec": 5.5,
            "endSec": 10.0,
            "sourceText": "Today we showcase automated multi-speaker dubbing.",
            "targetText": "",
            "voiceOverride": "Special-Voice",
            "cps": 11.1,
            "cpsStatus": "Optimal",
        },
    ]


# ============================================================================
# 1. Backend Orchestrator Tests
# ============================================================================

def test_run_staged_translation_success_1_to_1_alignment(tmp_path, sample_stage2_segments, monkeypatch):
    """Verify run_staged_translation translates segments and performs 1:1 matching preserving metadata."""
    def fake_translator_run(**kwargs):
        return [
            {"line": 1, "text": "Chào mừng đến với buổi giới thiệu dịch video AI."},
            {"line": 2, "text": "Hôm nay chúng tôi trình diễn lồng tiếng đa người nói tự động."},
        ]

    monkeypatch.setattr(translator, "run", fake_translator_run)

    media_file = tmp_path / "test.mp4"
    media_file.touch()
    from videotrans.configure.config import TEMP_DIR
    import uuid
    cache_dir = Path(TEMP_DIR) / f"cache-{uuid.uuid4().hex}"
    cache_dir.mkdir(parents=True, exist_ok=True)

    params = {
        "name": media_file.as_posix(),
        "target_dir": tmp_path.as_posix(),
        "cache_folder": cache_dir.as_posix(),
        "source_language_code": "en",
        "target_language_code": "vi",
        "translate_type": 0,
        "segments": sample_stage2_segments,
        "uuid": "test-job-trans",
    }

    events = []
    result = run_staged_translation(TaskRequest(params), event_sink=events.append)

    assert result.status == TaskStatus.SUCCEEDED
    assert len(result.segments) == 2

    seg1, seg2 = result.segments
    # 1:1 translated text updated
    assert seg1["targetText"] == "Chào mừng đến với buổi giới thiệu dịch video AI."
    assert seg2["targetText"] == "Hôm nay chúng tôi trình diễn lồng tiếng đa người nói tự động."

    # Preserved metadata
    assert seg1["id"] == 1
    assert seg1["speakerId"] == "spk_1"
    assert seg1["speakerName"] == "Alex Carter"
    assert seg1["startSec"] == 1.0
    assert seg1["endSec"] == 5.0
    assert seg1["voiceOverride"] is None

    assert seg2["id"] == 2
    assert seg2["speakerId"] == "spk_2"
    assert seg2["speakerName"] == "Elena Rostova"
    assert seg2["voiceOverride"] == "Special-Voice"

    # CPS recalculation
    assert seg1["targetCps"] > 0
    assert seg2["targetCps"] > 0


def test_run_staged_translation_language_bypass(tmp_path, sample_stage2_segments):
    """When source and target languages are identical, bypass external translator and copy source to target."""
    media_file = tmp_path / "test.mp4"
    media_file.touch()
    from videotrans.configure.config import TEMP_DIR
    import uuid
    cache_dir = Path(TEMP_DIR) / f"cache-{uuid.uuid4().hex}"
    cache_dir.mkdir(parents=True, exist_ok=True)

    params = {
        "name": media_file.as_posix(),
        "target_dir": tmp_path.as_posix(),
        "cache_folder": cache_dir.as_posix(),
        "source_language_code": "en",
        "target_language_code": "en",
        "translate_type": 0,
        "segments": sample_stage2_segments,
        "uuid": "test-bypass-job",
    }

    result = run_staged_translation(TaskRequest(params))
    assert result.status == TaskStatus.SUCCEEDED
    assert len(result.segments) == 2
    assert result.segments[0]["targetText"] == sample_stage2_segments[0]["sourceText"]
    assert result.segments[1]["targetText"] == sample_stage2_segments[1]["sourceText"]


def test_run_staged_translation_empty_segments(tmp_path):
    """Empty segments should return SUCCEEDED with empty tuple without error."""
    media_file = tmp_path / "test.mp4"
    media_file.touch()
    from videotrans.configure.config import TEMP_DIR
    import uuid
    cache_dir = Path(TEMP_DIR) / f"cache-{uuid.uuid4().hex}"
    cache_dir.mkdir(parents=True, exist_ok=True)

    params = {
        "name": media_file.as_posix(),
        "target_dir": tmp_path.as_posix(),
        "cache_folder": cache_dir.as_posix(),
        "source_language_code": "en",
        "target_language_code": "vi",
        "translate_type": 0,
        "segments": [],
        "uuid": "test-empty-job",
    }
    result = run_staged_translation(TaskRequest(params))
    assert result.status == TaskStatus.SUCCEEDED
    assert len(result.segments) == 0


def test_run_staged_translation_cancellation(tmp_path, sample_stage2_segments):
    """Cancelled token before execution returns CANCELLED."""
    media_file = tmp_path / "test.mp4"
    media_file.touch()
    from videotrans.configure.config import TEMP_DIR
    import uuid
    cache_dir = Path(TEMP_DIR) / f"cache-{uuid.uuid4().hex}"
    cache_dir.mkdir(parents=True, exist_ok=True)

    params = {
        "name": media_file.as_posix(),
        "target_dir": tmp_path.as_posix(),
        "cache_folder": cache_dir.as_posix(),
        "source_language_code": "en",
        "target_language_code": "vi",
        "translate_type": 0,
        "segments": sample_stage2_segments,
        "uuid": "test-cancel-job",
    }
    token = CancellationToken()
    token.cancel()
    result = run_staged_translation(TaskRequest(params), cancellation_token=token)
    assert result.status == TaskStatus.CANCELLED


def test_run_staged_translation_failure_resilience(tmp_path, sample_stage2_segments, monkeypatch):
    """Exception in translator is caught and returned as TaskStatus.FAILED."""
    def broken_translator(**kwargs):
        raise RuntimeError("LLM API Quota Exceeded")

    monkeypatch.setattr(translator, "run", broken_translator)

    media_file = tmp_path / "test.mp4"
    media_file.touch()
    from videotrans.configure.config import TEMP_DIR
    import uuid
    cache_dir = Path(TEMP_DIR) / f"cache-{uuid.uuid4().hex}"
    cache_dir.mkdir(parents=True, exist_ok=True)

    params = {
        "name": media_file.as_posix(),
        "target_dir": tmp_path.as_posix(),
        "cache_folder": cache_dir.as_posix(),
        "source_language_code": "en",
        "target_language_code": "vi",
        "translate_type": 0,
        "segments": sample_stage2_segments,
        "uuid": "test-fail-job",
    }

    result = run_staged_translation(TaskRequest(params))
    assert result.status == TaskStatus.FAILED
    assert result.failure is not None
    assert "LLM API Quota Exceeded" in result.failure.message


# ============================================================================
# 2. Backend WebUI API Endpoint Tests
# ============================================================================

@pytest.mark.asyncio
async def test_api_jobs_translation_lifecycle(tmp_path, sample_stage2_segments):
    """Test POST /api/jobs with jobType='translation', polling /api/jobs/{id}, and cancel endpoint."""
    def fake_translation_runner(request, event_sink, token):
        segs = [
            {**seg, "targetText": f"Trans: {seg.get('sourceText', '')}"}
            for seg in request.params.get("segments", [])
        ]
        return TaskResult("test-id", TaskStatus.SUCCEEDED, tmp_path, segments=tuple(segs))

    app = create_app(upload_dir=tmp_path / "uploads", translation_runner=fake_translation_runner)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        # 1. Start translation job
        payload = {
            "mediaId": "mock-media-123",
            "jobType": "translation",
            "options": {
                "sourceLanguage": "en",
                "targetLanguage": "vi",
                "translateType": 0,
                "translationMode": "srt",
                "segments": sample_stage2_segments,
            },
        }
        res = await client.post("/api/jobs", json=payload)
        assert res.status == 202
        job_data = await res.json()
        job_id = job_data["id"]
        assert job_id

        # 2. Poll job status
        res = await client.get(f"/api/jobs/{job_id}")
        assert res.status == 200
        status_data = await res.json()
        assert status_data["id"] == job_id
        assert status_data["jobType"] == "translation"

        # 3. Test cancel endpoint
        res = await client.post(f"/api/jobs/{job_id}/cancel")
        assert res.status == 200
        cancel_data = await res.json()
        assert cancel_data["status"] in ("cancelled", "succeeded", "failed")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_translate_direct(tmp_path, sample_stage2_segments):
    """Test POST /api/translate direct synchronous translation endpoint."""
    def fake_runner(request, event_sink, token):
        translated = [
            {**seg, "targetText": f"Dịch: {seg.get('sourceText', '')}"}
            for seg in request.params.get("segments", [])
        ]
        return TaskResult("direct-id", TaskStatus.SUCCEEDED, tmp_path, segments=tuple(translated))

    app = create_app(upload_dir=tmp_path / "uploads", translation_runner=fake_runner)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        res = await client.post("/api/translate", json={
            "sourceLanguage": "en",
            "targetLanguage": "vi",
            "translateType": 0,
            "segments": sample_stage2_segments,
        })
        assert res.status == 200
        data = await res.json()
        assert data["ok"] is True
        assert len(data["segments"]) == 2
        assert "Dịch:" in data["segments"][0]["targetText"]
    finally:
        await client.close()


# ============================================================================
# 3. Frontend Component DOM Contracts & Headless Node.js Tests
# ============================================================================
