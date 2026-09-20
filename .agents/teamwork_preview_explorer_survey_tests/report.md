# DubDub Stage 3: Voice & Dubbing — Testing & E2E Survey Report

**Author**: Testing & E2E Explorer  
**Date**: 2026-09-19  
**Status**: Complete  
**Scope**: Test infrastructure, existing test conventions, and proposed test suite architecture for Stage 3: Voice & Dubbing.

---

## 1. Executive Summary

This report establishes the testing strategy, test harness conventions, and test suite architecture for **Stage 3: Voice & Dubbing** in DubDub AI Video Dubbing Studio.

Based on thorough codebase investigation:
1. The repository uses `pytest` managed by `uv` (`uv run pytest`), running in Python 3.10 with fast execution (~2s to 3s for comprehensive test suites).
2. Backend HTTP endpoints are tested via `aiohttp.test_utils.TestClient` and `TestServer(app)` with dependency injection on `webui.create_app(...)`, completely avoiding live external network requests, real GPUs, or file pollution outside `tmp_path`.
3. Frontend components in `frontend/js/` are native ES modules without a Node build pipeline. Existing tests (`tests/test_webui.py` and `tests/test_staged_asr_and_transcript.py`) verify frontend components and reactive state machines using strict Python-based invariant inspections (contract checking, AST/regex assertions, reactive property binding). In addition, because Node v22 is installed on the host, headless ES-module render validation (`node --input-type=module`) is available as an optional supplementary check.
4. Stage 3 requires automated verification for:
   - Backend voice discovery endpoint (`/api/voices`) across all 4 TTS providers and target languages.
   - Speaker-to-voice mapping matrix and per-block voice override resolution & reset logic.
   - Reactive store state management and cross-stage persistence (`speakerVoiceMap`, `voiceOverride`, `targetText`).
   - Frontend UI rendering (teleprompter blocks, `MM:SS.mmm` timestamps, speaker badges, subtitle overlay on the video preview, and synchronized seek-and-play).

We propose creating a dedicated test suite in `tests/test_stage3_voice_dubbing.py` covering 24+ targeted test cases across 4 architectural layers.

---

## 2. Existing Testing Conventions & Infrastructure

### 2.1 Test Execution & Tooling
- **Test Runner**: `pytest` (version 9.0.3) invoked via `uv run pytest`.
- **Environment**: Python 3.10.19 (defined in `pyproject.toml` as `>=3.10, <3.11`).
- **Dev Dependencies**: `[dependency-groups] dev = ["pytest"]`.
- **Execution Speed**: Existing test suites run extremely fast:
  - `uv run pytest tests/test_staged_asr_and_transcript.py`: **23 tests passed in 2.02s**.
  - `uv run pytest tests/test_webui.py`: **22 tests passed in 3.37s**.

### 2.2 Dependency Isolation & Mocking Strategy (`tests/conftest.py`)
In `tests/conftest.py`, heavy packages (`PySide6`, `torch`, `elevenlabs`, `openai`, `deepgram`, `aiohttp`, `httpx`, `ten_vad`, `pydub`) are checked dynamically via `importlib.util.find_spec`. If any package is missing, lightweight `MagicMock` and exception class stubs are installed into `sys.modules`. This ensures tests never fail due to missing CUDA drivers, GUI frameworks, or cloud SDKs.

### 2.3 WebUI Endpoint Testing Pattern
All WebUI testing in `tests/test_webui.py` and `tests/test_staged_asr_and_transcript.py` follows an established pattern:
1. `webui.create_app(...)` exposes dependency-injection parameters:
   - `upload_dir`: `Path` (redirected to `tmp_path / "uploads"`)
   - `settings_store`: in-memory dict/object replacing global `app_params`
   - `job_manager`: mock `JobManager` with synchronous or event-signaled mock runners
   - `media_probe`: mock callable replacing FFmpeg `get_video_info`
   - `asr_tester`: mock callable replacing third-party ASR testing
   - `translation_tester`: mock callable replacing translation testing
   - `ocr_extractor`: mock callable replacing PaddleOCR frame extraction
2. In-process execution:
   ```python
   app = webui.create_app(upload_dir=tmp_path / "uploads", settings_store=fake_settings)
   async def scenario():
       client = TestClient(TestServer(app))
       await client.start_server()
       try:
           res = await client.get("/api/options")
           assert res.status == 200
           data = await res.json()
           assert ...
       finally:
           await client.close()
   asyncio.run(scenario())
   ```
   No real HTTP ports are bound; tests are isolated, deterministic, and network-free.

### 2.4 Frontend Verification Pattern
Because DubDub's frontend consists of vanilla JavaScript ES modules without a bundler, tests verify the frontend through Python-based static and semantic contract checks:
1. Reading `.js` files using `(Path(webui.FRONTEND_DIR) / "js" / ...).read_text(encoding="utf-8")`.
2. Asserting critical attributes, event listeners, and bindings:
   - Method declarations: `assert "seekAndPlay" in state_source`
   - Data attributes: `assert 'data-segment-card' in stage_source`
   - Interactive events: `assert 'onclick="window.dubDubStore.seekAndPlay(' in stage_source`
   - State properties: `assert "speakerVoiceMap" in state_source`
   - Styling and DOM structure: asserting dynamic classes for active cards, speaker badges, and timestamps.
3. This pattern avoids external Node/npm dependencies in CI while providing 100% reliable verification of frontend contracts.

---

## 3. Analysis of Stage 3 Requirements & Testability

### 3.1 Backend Voice Discovery Endpoint (`/api/voices`)
**Current Implementation in `webui.py` (lines 681-689)**:
```python
async def voices_handler(request: web.Request) -> web.Response:
    tts_type = _optional_index(request.query.get("ttsType"), len(tts.TTS_NAME_LIST))
    language = request.query.get("language", "")
    try:
        voices = role_menu(tts_type, langcode=language) or ["No"]
    except Exception:
        voices = ["No"]
    return web.json_response({"voices": voices})
```
**Supported Providers (`videotrans/tts/__init__.py`)**:
- `0`: ElevenLabs (`tts.ELEVENLABS_TTS`)
- `1`: OmniVoice (`tts.OMNIVOICE_TTS`)
- `2`: VieNeu-TTS (`tts.VIENEU_TTS` - default)
- `3`: Gemini TTS (`tts.GEMINI_TTS` - 30 roles in `GEMINITTS_ROLES`)

**Test Requirements for `/api/voices`**:
1. Querying with valid `ttsType` (0, 1, 2, 3) and `language` (e.g. `vi`, `en`, `zh-cn`) returns status 200 and a JSON list of voice names under key `"voices"`.
2. Defaulting behavior: missing `ttsType` or non-numeric `ttsType` falls back gracefully to default without 500 error.
3. Out-of-bounds `ttsType` (e.g., negative or 999) handled gracefully.
4. Exception resilience: if `role_menu` throws (e.g. ElevenLabs API failure or missing voice cache), returns `{"voices": ["No"]}` safely.
5. In-test mocking: `webui.role_menu` can be cleanly mocked via `monkeypatch.setattr(webui, "role_menu", ...)` to provide deterministic voice fixtures without network calls.

### 3.2 Global Speaker-to-Voice Mapping Matrix
**Requirements**:
- Dynamically detect all distinct speakers from `state.segments` (e.g., "Speaker 1", "Speaker 2").
- Assign a global voice to each distinct speaker in `state.speakerVoiceMap` (e.g., `{"Speaker 1": "Zephyr", "Speaker 2": "Puck"}`).
- Updating a speaker's voice propagates immediately to all dialog blocks belonging to that speaker that do not have an individual override.
- Persist in `window.dubDubStore` across workflow navigation.

**Test Requirements**:
1. Distinct speaker detection logic:
   - Multi-speaker transcript -> extracts all distinct speaker labels.
   - Single-speaker transcript -> extracts single speaker.
   - Mixed/legacy field support (`speakerLabel`, `speakerName`, `speaker`, `speakerId`).
2. Propagation logic:
   - When `speakerVoiceMap["Speaker 1"]` is updated to `"Voice B"`, all segments for `"Speaker 1"` resolve to `"Voice B"`.
   - Segments belonging to `"Speaker 2"` remain unchanged.
3. Persistence:
   - Moving from Step 2 to Step 3, then Step 4, and back to Step 3 preserves `state.speakerVoiceMap`.

### 3.3 Per-Block Voice Overrides & Reset Logic
**Requirements**:
- Each dialog block has a voice dropdown showing the speaker's assigned default (e.g., `"Voice A (Default)"`).
- Selecting a different voice sets `seg.voiceOverride = "Voice C"` and visually indicates the override.
- An overridden block displays a "Reset to Default" button.
- Clicking "Reset to Default" clears `seg.voiceOverride` and immediately reverts to the speaker's global assigned voice.
- Changing the global speaker voice in the upper console updates only non-overridden blocks; blocks with `seg.voiceOverride` retain their override.

**Test Requirements**:
1. Effective voice resolution algorithm:
   - If `seg.voiceOverride` is set -> effective voice is `seg.voiceOverride`, `isOverride == True`.
   - If `seg.voiceOverride` is not set -> effective voice is `speakerVoiceMap.get(speaker, defaultVoice)`, `isOverride == False`.
2. Override isolation: setting `voiceOverride` on segment 1 does NOT affect segment 2 (even if they share the same speaker).
3. Reset behavior: clearing `voiceOverride` restores the segment to the current global speaker voice.
4. Global update isolation: changing global speaker voice updates segments without override while preserving segments with override.

### 3.4 Translated Dialog Blocks & Inline Editing
**Requirements**:
- Teleprompter feed renders each segment with:
  1. `MM:SS.mmm` start and end timestamps.
  2. Speaker identifier / badge matching Stage 2 styling.
  3. Inline editable textarea for `targetText` (`seg.targetText`).
  4. Selected voice dropdown displaying default or override.
- Editing `targetText` updates `state.segments` in the store immediately and updates the video preview subtitle.

**Test Requirements**:
1. Text editing updates `seg.targetText` in the store.
2. Formatted time validation (`format_timestamp(startSec)` and `format_timestamp(endSec)`).
3. Pacing/CPS recalculation or preservation when `targetText` is modified.

### 3.5 Video Preview Subtitle Overlay & Synchronized Seek & Play
**Requirements**:
- Subtitle bar on the video canvas renders active segment's `targetText` with speaker badge during playback.
- Clicking any dialog card seeks `<video>` element to `startSec` and triggers continuous playback (`seekAndPlay(seg.startSec, seg.id)`).
- Playhead timecode updates synchronously with video playback.

**Test Requirements**:
1. VideoPlayer markup includes subtitle display showing `currentSegment.targetText` and speaker badge.
2. Teleprompter cards bind `onclick="window.dubDubStore.seekAndPlay(${seg.startSec}, ...)"`.
3. Active card styling (`active-teleprompter-card` or highlighted border) matches `state.activeSegmentId`.

---

## 4. Proposed Test Architecture: `tests/test_stage3_voice_dubbing.py`

We propose structuring the test suite into **5 clean modules/classes** within `tests/test_stage3_voice_dubbing.py`:

```
tests/test_stage3_voice_dubbing.py
├── Section 1: Algorithmic & State Resolution Tests (Unit)
│   ├── test_detect_distinct_speakers_from_segments
│   ├── test_resolve_effective_voice_default
│   ├── test_resolve_effective_voice_with_override
│   ├── test_speaker_voice_propagation_updates_non_overridden_only
│   ├── test_reset_voice_override_restores_global_voice
│   ├── test_speaker_voice_matrix_with_multiple_speakers
│   └── test_target_text_update_preserves_segment_metadata
│
├── Section 2: Backend Voice Discovery API Tests (/api/voices)
│   ├── test_voices_endpoint_returns_voices_for_each_provider
│   ├── test_voices_endpoint_passes_language_parameter
│   ├── test_voices_endpoint_handles_missing_and_invalid_ttstype
│   ├── test_voices_endpoint_handles_backend_exception_gracefully
│   ├── test_voices_endpoint_mock_integration_with_role_menu
│   └── test_api_options_contains_tts_defaults_and_providers
│
├── Section 3: Frontend Invariants & Store State Inspection
│   ├── test_frontend_state_initializes_speaker_voice_map
│   ├── test_frontend_state_has_voice_mapping_methods
│   ├── test_frontend_state_has_voice_override_and_reset_methods
│   ├── test_frontend_state_persists_across_stage_navigation
│   ├── test_frontend_state_load_voices_populates_roles
│   └── test_frontend_state_update_target_text_smooth_typing
│
├── Section 4: Frontend Component Rendering & DOM Contract Tests
│   ├── test_stage3_screen_renders_tts_provider_selector
│   ├── test_stage3_screen_renders_dynamic_speaker_casting_console
│   ├── test_stage3_teleprompter_renders_formatted_timestamps_and_badges
│   ├── test_stage3_teleprompter_renders_target_text_editor
│   ├── test_stage3_teleprompter_renders_voice_selector_and_reset_button
│   ├── test_stage3_teleprompter_binds_seek_and_play
│   └── test_video_player_renders_stage3_subtitle_and_speaker_badge
│
└── Section 5: Headless Node.js Render Validation (Optional / Conditional)
    └── test_stage3_component_executes_in_node_without_errors
```

---

## 5. Detailed Test Specifications & Sample Code

### 5.1 Test Fixtures (`conftest.py` or local in `test_stage3_voice_dubbing.py`)

```python
import pytest
from aiohttp.test_utils import TestClient, TestServer
import webui
from videotrans import tts

@pytest.fixture
def mock_voice_roles(monkeypatch):
    """Provides deterministic voice lists per TTS provider without network access."""
    catalogs = {
        tts.ELEVENLABS_TTS: ["No", "Rachel", "Domi", "Bella", "Antoni"],
        tts.OMNIVOICE_TTS: ["No", "clone", "Omni-Speaker-1", "Omni-Speaker-2"],
        tts.VIENEU_TTS: ["No", "clone", "Phạm Tuyên", "Mai Phương", "Custom: Voice1"],
        tts.GEMINI_TTS: ["Zephyr", "Puck", "Charon", "Kore", "Fenrir"],
    }
    
    def fake_role_menu(tts_type, langcode=None):
        return catalogs.get(tts_type, ["No"])
    
    monkeypatch.setattr(webui, "role_menu", fake_role_menu)
    return catalogs

@pytest.fixture
def sample_multi_speaker_segments():
    return [
        {
            "id": 1,
            "speakerId": "spk_1",
            "speakerName": "Alex Carter",
            "speakerLabel": "Speaker 1",
            "speakerCode": "AC",
            "speakerColor": "amber",
            "startTime": "00:01.000",
            "endTime": "00:04.000",
            "startSec": 1.0,
            "endSec": 4.0,
            "sourceText": "Welcome to our broadcast presentation.",
            "targetText": "Chào mừng đến với buổi phát sóng.",
            "voiceOverride": None,
        },
        {
            "id": 2,
            "speakerId": "spk_2",
            "speakerName": "Elena Rostova",
            "speakerLabel": "Speaker 2",
            "speakerCode": "ER",
            "speakerColor": "secondary",
            "startTime": "00:04.500",
            "endTime": "00:07.500",
            "startSec": 4.5,
            "endSec": 7.5,
            "sourceText": "Thank you Alex, thrilled to be here.",
            "targetText": "Cảm ơn Alex, rất vui được ở đây.",
            "voiceOverride": None,
        },
        {
            "id": 3,
            "speakerId": "spk_1",
            "speakerName": "Alex Carter",
            "speakerLabel": "Speaker 1",
            "speakerCode": "AC",
            "speakerColor": "amber",
            "startTime": "00:08.000",
            "endTime": "00:11.000",
            "startSec": 8.0,
            "endSec": 11.0,
            "sourceText": "Let's explore AI voice cloning today.",
            "targetText": "Hôm nay hãy cùng khám phá nhân bản giọng nói AI.",
            "voiceOverride": "Rachel",  # Per-block override on segment 3
        },
    ]
```

### 5.2 Algorithmic Logic & Voice Resolution Helper
The core business logic of voice resolution can be formalized and tested independently:

```python
def resolve_effective_voice(segment, speaker_voice_map, default_voice="No"):
    """
    Returns (effective_voice, is_overridden).
    If segment has a voiceOverride, returns (voiceOverride, True).
    Otherwise returns (speaker_voice_map[speaker], False).
    """
    override = segment.get("voiceOverride")
    if override:
        return override, True
    speaker = (
        segment.get("speakerLabel")
        or segment.get("speakerName")
        or segment.get("speaker")
        or "Speaker 1"
    )
    return speaker_voice_map.get(speaker, default_voice), False


def detect_distinct_speakers(segments):
    """Extract distinct speaker labels preserving first appearance order."""
    seen = set()
    result = []
    for s in segments:
        label = s.get("speakerLabel") or s.get("speakerName") or s.get("speaker") or "Speaker 1"
        if label not in seen:
            seen.add(label)
            result.append(label)
    return result or ["Speaker 1"]
```

### 5.3 Concrete Test Cases

#### 1. Voice Discovery Endpoint Tests
```python
def test_voices_endpoint_returns_voices_for_each_provider(tmp_path, mock_voice_roles):
    app = webui.create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            for tts_type, expected_voices in mock_voice_roles.items():
                res = await client.get(f"/api/voices?ttsType={tts_type}&language=vi")
                assert res.status == 200
                data = await res.json()
                assert "voices" in data
                assert data["voices"] == expected_voices
        finally:
            await client.close()

    asyncio.run(scenario())


def test_voices_endpoint_graceful_on_bad_params(tmp_path):
    app = webui.create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            # Missing ttsType
            res = await client.get("/api/voices")
            assert res.status == 200
            data = await res.json()
            assert isinstance(data.get("voices"), list)

            # Invalid string ttsType
            res = await client.get("/api/voices?ttsType=invalid_string")
            assert res.status == 200

            # Out of bounds ttsType
            res = await client.get("/api/voices?ttsType=99999")
            assert res.status == 200
            assert (await res.json())["voices"] == ["No"]
        finally:
            await client.close()

    asyncio.run(scenario())


def test_voices_endpoint_handles_role_menu_exception(tmp_path, monkeypatch):
    def failing_role_menu(*_args, **_kwargs):
        raise RuntimeError("External TTS connection timeout")

    monkeypatch.setattr(webui, "role_menu", failing_role_menu)
    app = webui.create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            res = await client.get("/api/voices?ttsType=0&language=en")
            assert res.status == 200
            assert (await res.json()) == {"voices": ["No"]}
        finally:
            await client.close()

    asyncio.run(scenario())
```

#### 2. Speaker-to-Voice Mapping & Override Resolution Tests
```python
def test_speaker_voice_mapping_propagation_and_override():
    segments = [
        {"id": 1, "speakerLabel": "Speaker 1", "voiceOverride": None},
        {"id": 2, "speakerLabel": "Speaker 1", "voiceOverride": None},
        {"id": 3, "speakerLabel": "Speaker 1", "voiceOverride": "Rachel"},  # Overridden
        {"id": 4, "speakerLabel": "Speaker 2", "voiceOverride": None},
    ]
    mapping = {"Speaker 1": "Zephyr", "Speaker 2": "Puck"}

    # Initial resolution
    assert resolve_effective_voice(segments[0], mapping) == ("Zephyr", False)
    assert resolve_effective_voice(segments[1], mapping) == ("Zephyr", False)
    assert resolve_effective_voice(segments[2], mapping) == ("Rachel", True)
    assert resolve_effective_voice(segments[3], mapping) == ("Puck", False)

    # Change Speaker 1 global voice to "Charon"
    mapping["Speaker 1"] = "Charon"

    # Segments 1 & 2 update; Segment 3 remains on "Rachel"
    assert resolve_effective_voice(segments[0], mapping) == ("Charon", False)
    assert resolve_effective_voice(segments[1], mapping) == ("Charon", False)
    assert resolve_effective_voice(segments[2], mapping) == ("Rachel", True)

    # Reset Segment 3 override
    segments[2]["voiceOverride"] = None
    assert resolve_effective_voice(segments[2], mapping) == ("Charon", False)
```

#### 3. Frontend Invariant & UI Contract Tests
```python
def test_frontend_state_has_stage3_voice_dubbing_contracts():
    state_source = (Path(webui.FRONTEND_DIR) / "js" / "state.js").read_text(encoding="utf-8")

    # Reactive store properties
    assert "speakerVoiceMap" in state_source
    assert "updateSpeakerVoiceMap" in state_source or "setSpeakerVoice" in state_source
    assert "setSegmentVoiceOverride" in state_source or "updateSegmentVoiceOverride" in state_source
    assert "resetSegmentVoiceOverride" in state_source or "resetVoiceOverride" in state_source
    assert "loadVoices" in state_source
    assert "/api/voices" in state_source


def test_stage3_screen_renders_all_required_controls():
    stage3_source = (Path(webui.FRONTEND_DIR) / "js" / "screens" / "Stage3VoiceDubbing.js").read_text(encoding="utf-8")
    player_source = (Path(webui.FRONTEND_DIR) / "js" / "components" / "VideoPlayer.js").read_text(encoding="utf-8")

    # Dedicated TTS provider console & voice loading
    assert "backend.config.ttsType" in stage3_source or "options.voices" in stage3_source
    assert "loadVoices" in stage3_source or "updateBackendConfig" in stage3_source

    # Dynamic speaker casting console
    assert "speakerVoiceMap" in stage3_source or "speakers" in stage3_source
    assert "setSpeakerVoice" in stage3_source or "updateSpeakerVoiceMap" in stage3_source

    # Teleprompter feed
    assert "targetText" in stage3_source
    assert "startTime" in stage3_source and "endTime" in stage3_source
    assert "voiceOverride" in stage3_source or "Default" in stage3_source
    assert "reset" in stage3_source.lower() or "Reset to Default" in stage3_source

    # Video seeking click handler
    assert "seekAndPlay" in stage3_source

    # Subtitle bar on video player
    assert "targetText" in player_source
```

#### 4. Optional Headless Node.js Execution Test
```python
import json
import shutil
import subprocess

def test_stage3_renders_valid_html_via_node():
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js not installed")

    mock_state = {
        "currentStep": 3,
        "activeSegmentId": 1,
        "languages": {"source": {"name": "English"}, "target": {"name": "Vietnamese", "code": "vi"}},
        "backend": {
            "options": {"languages": [], "voices": [[0, "ElevenLabs"], [2, "VieNeu-TTS"]], "voiceRoles": ["Voice A", "Voice B"]},
            "config": {"ttsType": 2, "voiceRole": "Voice A"},
            "outputs": [],
        },
        "speakerVoiceMap": {"Speaker 1": "Voice A"},
        "speakers": [{"id": "spk_1", "code": "S1", "name": "Speaker 1"}],
        "playback": {"currentTime": 0, "formattedTime": "00:00.000", "isPlaying": false, "audioChannel": "dub"},
        "project": {"resolution": "1920x1080", "fps": "30", "duration": "00:10.000"},
        "tuning": {"pace": 1.0, "timbreWarmth": 50},
        "lockedTerms": [],
        "segments": [
            {
                "id": 1,
                "speakerLabel": "Speaker 1",
                "speakerCode": "S1",
                "speakerColor": "amber",
                "startTime": "00:00.000",
                "endTime": "00:03.000",
                "startSec": 0.0,
                "endSec": 3.0,
                "sourceText": "Hello world",
                "targetText": "Xin chao the gioi",
                "voiceOverride": None,
                "cps": 10.0,
                "cpsStatus": "Optimal",
            }
        ]
    }

    script = f"""
    import {{ renderStage3VoiceDubbing }} from './frontend/js/screens/Stage3VoiceDubbing.js';
    const state = {json.dumps(mock_state)};
    const html = renderStage3VoiceDubbing(state);
    if (!html || typeof html !== 'string' || html.length < 50) {{
        process.exit(1);
    }}
    console.log('SUCCESS');
    """
    proc = subprocess.run([node_exe, "--input-type=module", "-e", script], capture_output=True, text=True)
    assert proc.returncode == 0
    assert "SUCCESS" in proc.stdout
```

---

## 6. Implementation Readiness & Risk Mitigation

| Risk / Challenge | Cause | Mitigation / Test Defense |
|---|---|---|
| **External Network Latency or Flakiness** | Calling real ElevenLabs / Gemini APIs in tests | TestClient + in-memory mocks (`mock_voice_roles` fixture) ensure 0 network calls and <10ms response times. |
| **Divergence between Stage 2 and Stage 3 Segment State** | Segments mutated or overwritten during stage navigation | Test store persistence across step switching (`currentStep: 2 -> 3 -> 4 -> 3`). |
| **Overridden Voice Accidental Overwrite** | Changing global speaker voice wiping out custom per-block voice overrides | Rigorous unit tests specifically asserting that overridden blocks retain their assigned voice when global speaker voice changes. |
| **Subtitles Lagging Video Playhead** | Timecode mismatch or wrong segment lookup in `VideoPlayer.js` | Unit tests verifying `currentSegment` resolution matches `activeSegmentId` and playhead seek triggers playback. |
| **CI Environment Without Node.js** | In some CI runners, Node may not be installed | Primary verification uses Python AST / source inspection; Node rendering test is conditionally skipped via `pytest.importorskip` or `shutil.which("node")`. |

---

## 7. Next Steps for Implementers

1. **Frontend State (`frontend/js/state.js`)**:
   - Add `speakerVoiceMap: {}` to initial state.
   - Implement `setSpeakerVoice(speaker, voice)` (or `updateSpeakerVoiceMap`).
   - Implement `setSegmentVoiceOverride(segmentId, voice)`.
   - Implement `resetSegmentVoiceOverride(segmentId)`.
   - Implement `updateSegmentTargetText(segmentId, text)`.
   - Connect `loadVoices()` trigger to provider and language changes.
2. **Stage 3 View (`frontend/js/screens/Stage3VoiceDubbing.js`)**:
   - Replace static speaker profiles with dynamic speaker casting console mapped from `detectDistinctSpeakers(state.segments)`.
   - Connect upper-right TTS provider select to `/api/voices`.
   - Bind teleprompter feed to render dynamic segment blocks with editable `targetText`, formatted times, voice dropdown showing default or override, reset button, and click-to-seek (`seekAndPlay`).
3. **Video Player (`frontend/js/components/VideoPlayer.js`)**:
   - Ensure bottom subtitle bar renders the active segment's `targetText` with speaker badge.
4. **Test Suite (`tests/test_stage3_voice_dubbing.py`)**:
   - Implement the test cases specified in Section 5.
   - Run `uv run pytest tests/test_stage3_voice_dubbing.py` and verify all tests pass.
