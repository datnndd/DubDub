## 2026-09-20T03:11:53Z

You are a Test Writer subagent for DubDub AI Video Dubbing Studio Stage 4 Redesign.
Your identity: test_writer_s4
Your working directory: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_test_writer_s4
Original Request path: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\ORIGINAL_REQUEST.md
Project Scope path: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_orchestrator_2\PROJECT.md
Survey Tests path: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_tests_s4\survey_tests.md

MANDATORY FIRST STEP: Read c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\ORIGINAL_REQUEST.md (specifically section ## 2026-09-20T03:04:42Z). Do not summarize or skip reading it. Also read the Survey Tests path.

Scope & Exclusively Owned File:
You exclusively own: `tests/test_stage4_edit_video.py`. DO NOT modify files owned by the worker (`frontend/js/screens/Stage4EditVideo.js`, `frontend/js/state.js`, `webui.py`).

Mission:
Expand `tests/test_stage4_edit_video.py` into a comprehensive, highly reliable automated test suite verifying all requirements R1–R5 and Acceptance Criteria of Stage 4.

Follow the 6-section test architecture established in `survey_tests.md`:
1. Section 1: Backend API Endpoints & Asset Ingestion
   - Test `POST /api/assets/background-audio` and `POST /api/assets/thumbnail` with valid and invalid extensions (.exe, .txt, .sh rejected with 400).
   - Test missing `X-Filename` header rejection.
   - Test asset registration in `EDIT_ASSETS`.
2. Section 2: Task Configuration & Render Parameters
   - Test `webui.build_task_params` with `job_type="render"`:
     * Mapping of `originalAudioVolume` (0.0–1.5) to `source_audio_volume`.
     * Mapping of `backgroundAudioVolume` (0.0–1.5) to `backaudio_volume`.
     * Mapping of `volume` (dubbed voice volume).
     * Resolution of `backgroundAudioId` to `background_music` path.
     * Resolution of `thumbnailId` to `thumbnail` path.
     * Setting of `subtitle_style` dictionary and ASS conversion compatibility.
     * `options.subtitles` bypass of ASR/translation stages.
3. Section 3: Store State Logic & Boundaries
   - Audio mix clamping between 0 and 150.
   - Mute toggle state caching and restoration.
   - Subtitle font size clamping (e.g. 8 to 64).
   - Inline subtitle editing and startSec/endSec boundary validation (`startSec < endSec`).
   - SRT serialization (`serializeEditedSrt`) creating valid standard SRT blocks.
4. Section 4: Frontend DOM Contracts & Invariants
   - 3-area layout structure (`[data-stage4-studio]`, Upper Deck widescreen preview + inspector, Lower Deck timeline).
   - Unboxed canvas subtitle overlay without teleprompter card wrapping, `#FFFFFF` text color, 2px outline, subtle shadow.
   - Multi-track timeline lanes: Video, Subtitles, Dubbed TTS, BGM.
   - Interactive playhead needle `[data-timeline-playhead]`.
   - Audio mix sliders (0–150%) and mute toggles.
   - BGM preview audio element `#stage4-bgm-preview` and input `#stage4-background-input`.
   - Thumbnail upload input `#stage4-thumbnail-input` and aspect-video preview card `[data-thumbnail-preview]`.
   - Dynamic font size slider `[data-action="update-font-size"]` AND number input `[data-action="update-font-size-input"]`.
5. Section 5: Headless Node.js ES Module Evaluation
   - Using `shutil.which("node")` with `pytest.skip` if Node is not available, evaluate `Stage4EditVideo.js` and `state.js` in a headless Node process.
6. Section 6: End-to-End Integration & Workflow Scenarios
   - Simulate complete Stage 4 workflow: load dubbed video -> edit subtitle text and timestamps -> adjust audio mix levels -> upload BGM -> set thumbnail -> export payload verification.

Verification & Delivery:
- Run `uv run pytest tests/test_stage4_edit_video.py -v` to ensure all tests pass.
- Write `TEST_READY.md` in root or your working directory summarizing test counts across Tiers 1-4.
- Write `handoff.md` in your working directory with Observation, Logic Chain, Caveats, Conclusion, and Verification Method.
- Send a completion message to your parent.
