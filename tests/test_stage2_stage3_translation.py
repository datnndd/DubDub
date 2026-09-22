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
import json
from pathlib import Path
import shutil
import subprocess
from unittest.mock import MagicMock

from aiohttp.test_utils import TestClient, TestServer
import pytest

import webui
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

    app = webui.create_app(upload_dir=tmp_path / "uploads", translation_runner=fake_translation_runner)
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

    app = webui.create_app(upload_dir=tmp_path / "uploads", translation_runner=fake_runner)
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

def test_status_footer_stage2_proceed_contract():
    """Verify StatusFooter for Stage 2 renders 'Proceed to Voice & Dubbing' with data-action-proceed."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    test_script = """
    globalThis.window = globalThis;
    globalThis.document = { querySelector: () => null, querySelectorAll: () => [] };

    const { renderStatusFooter } = await import('./frontend/js/components/StatusFooter.js');

    const state = {
        currentStep: 2,
        backend: { status: 'idle', message: '', error: null, outputs: [], asrDuration: 5.2 },
        project: { verified: true },
        translationModal: { active: false }
    };

    const html = renderStatusFooter(state);
    const checks = [
        ['action-proceed-attr', html.includes('data-action-proceed="proceed-to-voice"')],
        ['action-next-step-attr', html.includes('data-action="next-step"')],
        ['proceed-text', html.includes('Proceed to Voice &amp; Dubbing') || html.includes('Proceed to Voice & Dubbing')],
        ['proceed-store-call', html.includes('window.dubDubStore.proceedToVoiceDubbing()')],
    ];

    for (const [name, passed] of checks) {
        if (!passed) {
            console.error(`Check failed: ${name}`);
            process.exit(1);
        }
    }

    // Also check disabled state when modal is active
    state.translationModal.active = true;
    const disabledHtml = renderStatusFooter(state);
    if (!disabledHtml.includes('disabled')) {
        console.error('Check failed: button should be disabled when translation modal is active');
        process.exit(1);
    }

    console.log("STATUS_FOOTER_CONTRACTS_PASSED");
    """
    res = subprocess.run([node_exe, "--input-type=module", "-e", test_script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node script failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "STATUS_FOOTER_CONTRACTS_PASSED" in res.stdout


def test_stage2_modal_and_error_dom_contracts():
    """Verify Stage2ReviewTranscript renders loading modal and error banner when appropriate."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    test_script = """
    globalThis.window = globalThis;
    globalThis.document = { querySelector: () => null, querySelectorAll: () => [] };

    const { renderStage2ReviewTranscript } = await import('./frontend/js/screens/Stage2ReviewTranscript.js');

    const state = {
        currentStep: 2,
        project: { verified: true, filename: 'test.mp4' },
        backend: {
            status: 'idle',
            message: '',
            error: null,
            outputs: [],
            config: { translateType: 0, translationMode: 'srt' },
            options: { translationProviders: [{ translateType: 0, label: 'DeepLX', model: 'deeplx-pro' }], translationModes: [] }
        },
        languages: { source: { code: 'en', name: 'English' }, target: { code: 'vi', name: 'Vietnamese' } },
        playback: { formattedTime: '00:00.000', currentTime: 0 },
        segments: [{ id: 1, startSec: 0, endSec: 2, sourceText: 'Hello', targetText: '', speakerCode: 'S1' }],
        translationModal: { active: true, status: 'running', progress: 45, message: 'Translating segment 1 of 5...' },
        translationError: null,
        engines: { speakerDiarization: false }
    };

    const htmlWithModal = renderStage2ReviewTranscript(state);
    const modalChecks = [
        ['modal-attr', htmlWithModal.includes('data-translation-modal')],
        ['spinner-attr', htmlWithModal.includes('data-translation-spinner')],
        ['progress-attr', htmlWithModal.includes('data-translation-progress')],
        ['cancel-action-attr', htmlWithModal.includes('data-action="cancel-translation"')],
        ['cancel-attr', htmlWithModal.includes('data-translation-cancel')],
        ['progress-pct', htmlWithModal.includes('45%')],
        ['target-lang-label', htmlWithModal.includes('Vietnamese')],
    ];

    for (const [name, passed] of modalChecks) {
        if (!passed) {
            console.error(`Modal check failed: ${name}`);
            process.exit(1);
        }
    }

    // Test Error Banner rendering
    state.translationModal.active = false;
    state.translationError = 'LLM API rate limit exceeded. Please retry.';
    const htmlWithError = renderStage2ReviewTranscript(state);
    if (!htmlWithError.includes('data-translation-error')) {
        console.error('Error banner check failed: missing data-translation-error');
        process.exit(1);
    }
    if (!htmlWithError.includes('data-action="dismiss-translation-error"')) {
        console.error('Error banner check failed: missing dismiss button');
        process.exit(1);
    }
    if (!htmlWithError.includes('LLM API rate limit exceeded')) {
        console.error('Error banner check failed: message not rendered');
        process.exit(1);
    }

    console.log("STAGE2_DOM_CONTRACTS_PASSED");
    """
    res = subprocess.run([node_exe, "--input-type=module", "-e", test_script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node script failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "STAGE2_DOM_CONTRACTS_PASSED" in res.stdout


def test_headless_node_translation_bypass_scenarios():
    """Verify WorkflowStore language bypass and pre-populated segments bypass in Node."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    test_script = """
    globalThis.window = globalThis;
    globalThis.document = { querySelector: () => null, querySelectorAll: () => [] };

    const { store } = await import('./frontend/js/state.js');

    // SCENARIO 1: Same source and target language (e.g. en -> en)
    store.state.currentStep = 2;
    store.state.languages.source = { code: 'en', name: 'English' };
    store.state.languages.target = { code: 'en', name: 'English' };
    store.state.segments = [
        { id: 1, startSec: 0, endSec: 3, sourceText: 'Good morning', targetText: '', speakerId: 'spk_1' }
    ];

    await store.proceedToVoiceDubbing();

    if (store.state.currentStep !== 3) {
        console.error('Scenario 1 failed: step should be 3, got', store.state.currentStep);
        process.exit(1);
    }
    if (store.state.segments[0].targetText !== 'Good morning') {
        console.error('Scenario 1 failed: targetText not copied from sourceText');
        process.exit(1);
    }
    if (store.state.translationModal.active) {
        console.error('Scenario 1 failed: modal should not be active');
        process.exit(1);
    }

    // SCENARIO 2: All segments already have targetText
    store.state.currentStep = 2;
    store.state.languages.source = { code: 'en', name: 'English' };
    store.state.languages.target = { code: 'vi', name: 'Vietnamese' };
    store.state.segments = [
        { id: 1, startSec: 0, endSec: 3, sourceText: 'Good morning', targetText: 'Chào buổi sáng', speakerId: 'spk_1' },
        { id: 2, startSec: 3, endSec: 6, sourceText: 'Good evening', targetText: 'Chào buổi tối', speakerId: 'spk_1' }
    ];

    await store.proceedToVoiceDubbing();

    if (store.state.currentStep !== 3) {
        console.error('Scenario 2 failed: step should be 3, got', store.state.currentStep);
        process.exit(1);
    }
    if (store.state.translationModal.active) {
        console.error('Scenario 2 failed: modal should not be active');
        process.exit(1);
    }

    console.log("BYPASS_SCENARIOS_PASSED");
    """
    res = subprocess.run([node_exe, "--input-type=module", "-e", test_script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node script failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "BYPASS_SCENARIOS_PASSED" in res.stdout


def test_headless_node_translation_complete_and_stage3_sync_workflow():
    """Verify full translation workflow: start -> mock api -> complete -> Stage 3 sync and display."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    test_script = """
    globalThis.window = globalThis;
    globalThis.document = { querySelector: () => null, querySelectorAll: () => [] };

    // Mock fetch for translation API
    globalThis.fetch = async (url, opts = {}) => {
        if (url.includes('/api/jobs')) {
            return {
                ok: true,
                json: async () => ({
                    id: 'job-trans-test-1',
                    status: 'succeeded',
                    result: {
                        segments: [
                            { id: 1, targetText: 'Đoạn dịch một' },
                            { id: 2, targetText: 'Đoạn dịch hai' }
                        ]
                    }
                })
            };
        }
        return { ok: true, json: async () => ({}) };
    };

    const { store } = await import('./frontend/js/state.js');
    const { renderStage3VoiceDubbing } = await import('./frontend/js/screens/Stage3VoiceDubbing.js');

    store.state.currentStep = 2;
    store.state.languages.source = { code: 'en', name: 'English' };
    store.state.languages.target = { code: 'vi', name: 'Vietnamese' };
    store.state.backend.options.voiceRoles = ['Voice-Alpha', 'Voice-Beta'];
    store.state.segments = [
        { id: 1, speakerId: 'spk_1', speakerName: 'Presenter', startSec: 0, endSec: 4, sourceText: 'Segment one', targetText: '', voiceOverride: 'Custom-V1' },
        { id: 2, speakerId: 'spk_2', speakerName: 'Guest', startSec: 4, endSec: 8, sourceText: 'Segment two', targetText: '' }
    ];

    // Trigger translation
    await store.proceedToVoiceDubbing();

    // 1. Check Step transitioned to 3
    if (store.state.currentStep !== 3) {
        console.error('Expected currentStep to be 3, got', store.state.currentStep);
        process.exit(1);
    }

    // 2. Check 1:1 segment targetText update
    if (store.state.segments[0].targetText !== 'Đoạn dịch một') {
        console.error('Seg 1 targetText mismatch:', store.state.segments[0].targetText);
        process.exit(1);
    }
    if (store.state.segments[1].targetText !== 'Đoạn dịch hai') {
        console.error('Seg 2 targetText mismatch:', store.state.segments[1].targetText);
        process.exit(1);
    }

    // 3. Check preserved metadata
    if (store.state.segments[0].voiceOverride !== 'Custom-V1') {
        console.error('voiceOverride was not preserved');
        process.exit(1);
    }
    if (store.state.segments[0].speakerName !== 'Presenter') {
        console.error('speakerName was not preserved');
        process.exit(1);
    }

    // 4. Check speaker voice map populated
    if (!store.state.speakerVoiceMap['spk_1'] || !store.state.speakerVoiceMap['spk_2']) {
        console.error('speakerVoiceMap was not populated for distinct speakers');
        process.exit(1);
    }

    // 5. Render Stage 3 and check that teleprompter displays translated text
    const stage3Html = renderStage3VoiceDubbing(store.state);
    if (!stage3Html.includes('Đoạn dịch một')) {
        console.error('Stage 3 teleprompter does not display segment 1 translated text');
        process.exit(1);
    }
    if (!stage3Html.includes('Đoạn dịch hai')) {
        console.error('Stage 3 teleprompter does not display segment 2 translated text');
        process.exit(1);
    }

    console.log("TRANSLATION_STAGE3_SYNC_PASSED");
    """
    res = subprocess.run([node_exe, "--input-type=module", "-e", test_script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node script failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "TRANSLATION_STAGE3_SYNC_PASSED" in res.stdout


def test_headless_node_cancellation_and_error_handling_workflow():
    """Verify cancellation leaves user on Stage 2 and error displays error banner without data loss."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    test_script = """
    globalThis.window = globalThis;
    globalThis.document = { querySelector: () => null, querySelectorAll: () => [] };

    let failRequest = false;
    globalThis.fetch = async (url, opts = {}) => {
        if (failRequest) {
            return {
                ok: false,
                text: async () => 'Translation service rate limit reached'
            };
        }
        return {
            ok: true,
            json: async () => ({ id: 'mock-job-id', status: 'running' })
        };
    };

    const { store } = await import('./frontend/js/state.js');

    // 1. Test Cancellation
    store.state.currentStep = 2;
    store.state.languages.source = { code: 'en', name: 'English' };
    store.state.languages.target = { code: 'vi', name: 'Vietnamese' };
    store.state.segments = [
        { id: 1, startSec: 0, endSec: 3, sourceText: 'Original text', targetText: '', speakerId: 'spk_1' }
    ];

    // Start running
    const promise = store.proceedToVoiceDubbing();
    if (!store.state.translationModal.active) {
        console.error('Modal should be active while running');
        process.exit(1);
    }

    // Cancel
    await store.cancelTranslation();
    if (store.state.currentStep !== 2) {
        console.error('User should stay on Stage 2 after cancellation, got', store.state.currentStep);
        process.exit(1);
    }
    if (store.state.translationModal.active) {
        console.error('Modal should be closed after cancel');
        process.exit(1);
    }
    if (store.state.segments[0].sourceText !== 'Original text') {
        console.error('Original segment data was lost');
        process.exit(1);
    }

    // 2. Test Error Handling
    failRequest = true;
    await store.proceedToVoiceDubbing();

    if (store.state.currentStep !== 2) {
        console.error('User should stay on Stage 2 after error, got', store.state.currentStep);
        process.exit(1);
    }
    if (store.state.translationModal.active) {
        console.error('Modal should be closed after error');
        process.exit(1);
    }
    if (!store.state.translationError || !store.state.translationError.includes('rate limit')) {
        console.error('translationError was not set properly:', store.state.translationError);
        process.exit(1);
    }

    // Dismiss error
    store.dismissTranslationError();
    if (store.state.translationError !== null) {
        console.error('dismissTranslationError did not clear error');
        process.exit(1);
    }

    console.log("CANCEL_AND_ERROR_HANDLING_PASSED");
    """
    res = subprocess.run([node_exe, "--input-type=module", "-e", test_script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node script failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "CANCEL_AND_ERROR_HANDLING_PASSED" in res.stdout
