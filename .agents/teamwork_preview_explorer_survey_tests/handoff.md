# Handoff Report — Stage 3: Voice & Dubbing Test Architecture

## 1. Observation
1. **Test Runner & Configuration**:
   - `pyproject.toml` lines 240-243 define `[dependency-groups] dev = ["pytest"]`.
   - Running `uv run pytest tests/test_staged_asr_and_transcript.py` resulted in `23 passed, 36 warnings in 2.02s`.
   - Running `uv run pytest tests/test_webui.py` resulted in `22 passed, 42 warnings in 3.37s`.
2. **Dependency Isolation & Stubs**:
   - `tests/conftest.py` lines 8-35 dynamically check packages (`PySide6`, `torch`, `elevenlabs`, `openai`, `aiohttp`, etc.) via `importlib.util.find_spec`. Lines 36-147 stub missing packages with `MagicMock` and exception types so tests run without full hardware or GUI dependencies.
3. **WebUI Endpoint Testing Pattern**:
   - `tests/test_webui.py` lines 195-204 and `tests/test_staged_asr_and_transcript.py` lines 374-386 show that endpoints are tested using `aiohttp.test_utils.TestClient(TestServer(app))` inside `asyncio.run(scenario())` with dependency injection via `webui.create_app(...)`.
4. **Backend Voice Discovery Endpoint**:
   - `webui.py` lines 681-689 define `voices_handler` handling `GET /api/voices`:
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
   - In `videotrans/tts/__init__.py` lines 8-11:
     `ELEVENLABS_TTS = 0`, `OMNIVOICE_TTS = 1`, `VIENEU_TTS = 2`, `GEMINI_TTS = 3`.
5. **Frontend State & Components**:
   - `frontend/js/state.js` lines 513-526 implement `loadVoices()` querying `/api/voices?ttsType=...&language=...`.
   - `frontend/js/state.js` lines 13-159 currently lack `speakerVoiceMap`, per-block `voiceOverride`, and dedicated actions for speaker voice casting and override reset.
   - `frontend/js/screens/Stage3VoiceDubbing.js` lines 10-12 and 86-109 currently hardcode static speaker profiles ("Alex Carter", "Elena Rostova") rather than dynamically mapping distinct speakers from `state.segments`.
   - `frontend/js/components/VideoPlayer.js` line 17 defines `currentSegment = state.segments.find(s => String(s.id) === String(state.activeSegmentId)) || state.segments[0] || {};` and lines 225-248 render the subtitle overlay.
6. **Node.js Environment**:
   - Command `node -v` output: `v22.20.0`.
   - Command `node --input-type=module -e "import { renderStage3VoiceDubbing } from './frontend/js/screens/Stage3VoiceDubbing.js'; console.log('Import successful!');"` exited with code 0.

## 2. Logic Chain
1. From Observation 1, `uv run pytest` is the fast, native test runner for this repo, executing suites in 2-3 seconds. All tests must be runnable through `uv run pytest`.
2. From Observation 2, `tests/conftest.py` provides dependency stubs, ensuring that tests in `tests/test_stage3_voice_dubbing.py` will not crash due to missing optional third-party packages.
3. From Observation 3 and 4, `/api/voices` can be tested using `TestClient(TestServer(app))` with `webui.role_menu` monkeypatched to return deterministic catalogs. This avoids hitting live ElevenLabs or Gemini APIs and runs in sub-10ms.
4. From Observation 5, the frontend implementation requirements for Stage 3 (speaker-to-voice mapping, per-block overrides, reset, dynamic casting console, synchronized seek-and-play, and video preview subtitle) map to verifiable contracts in `state.js`, `Stage3VoiceDubbing.js`, and `VideoPlayer.js`.
5. From Observation 1 and 6, tests should follow the established pattern of inspecting JavaScript files via Python while providing an optional headless Node execution test for direct DOM/HTML string verification when Node is present.

## 3. Caveats
- Production synthesis (`dubbing.py`) requires actual audio engine execution and weights; test suite focuses on voice configuration, mapping propagation, overrides, and endpoint/UI contracts, mocking out TTS model execution.
- If running in an environment without Node.js, the optional Node execution test will be skipped cleanly via `shutil.which("node")`, falling back entirely to Python-based invariant inspections.

## 4. Conclusion
Stage 3 testing should be implemented in `tests/test_stage3_voice_dubbing.py` comprising 4 primary test sections:
1. Pure unit tests for distinct speaker detection, voice resolution, propagation, and override/reset logic.
2. Endpoint integration tests for `GET /api/voices` covering all 4 TTS providers, parameter edge cases, and exception handling.
3. Frontend invariant and contract tests asserting state store methods and reactive bindings across `state.js`, `Stage3VoiceDubbing.js`, and `VideoPlayer.js`.
4. Component rendering tests verifying formatted timestamps, speaker badges, inline `targetText` editing, and video seek-and-play triggers.

All proposed tests are documented with code examples and test plans in `report.md`.

## 5. Verification Method
To verify this survey and the proposed test architecture:
1. Inspect the survey report at:
   `c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_tests\report.md`
2. Run existing baseline tests to confirm environment health:
   `uv run pytest tests/test_staged_asr_and_transcript.py`
   `uv run pytest tests/test_webui.py`
3. After implementation of `tests/test_stage3_voice_dubbing.py`, verify that all tests pass with:
   `uv run pytest tests/test_stage3_voice_dubbing.py`
