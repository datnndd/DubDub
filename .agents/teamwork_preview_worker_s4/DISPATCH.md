## 2026-09-20T03:11:53Z

You are a Worker subagent for DubDub AI Video Dubbing Studio Stage 4 Redesign.
Your identity: worker_stage4
Your working directory: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_worker_s4
Original Request path: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\ORIGINAL_REQUEST.md
Project Scope path: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_orchestrator_2\PROJECT.md
Survey FE path: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_fe_s4\survey_fe.md
Survey BE path: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_be_s4\survey_be.md

MANDATORY FIRST STEP: Read c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\ORIGINAL_REQUEST.md (specifically section ## 2026-09-20T03:04:42Z). Do not summarize or skip reading it. Also read the Survey FE and Survey BE paths.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Scope & Exclusively Owned Files:
You exclusively own:
- `frontend/js/screens/Stage4EditVideo.js`
- `frontend/js/state.js`
- `frontend/js/components/VideoPlayer.js` (if any adjustments needed)
- `webui.py`
DO NOT modify test files (`tests/test_stage4_edit_video.py` is owned by the test writer).

Mission & Required Implementations:
1. Subtitle Typing Focus Polish (Fix Bug from FE Survey):
   - In `frontend/js/screens/Stage4EditVideo.js`: Add `data-segment-input="stage4-${esc(active?.id)}"` to the active subtitle textarea alongside `data-stage4-subtitle`.
   - In `frontend/js/state.js`: Update `updateSegmentTargetText` (and anywhere checking typing focus) to support `stage4-` prefix so typing in Stage 4 preserves input focus without triggering re-render blur.
2. Subtitle Typography Controls (R4):
   - In `frontend/js/screens/Stage4EditVideo.js`: In the Subtitles tab of the inspector, provide both a dynamic font size slider (`[data-action="update-font-size"]`) AND a synchronized number input (`[data-action="update-font-size-input"]`), min 8, max 64, step 1, default 22, updating preview canvas immediately.
3. Multi-Track Timeline & Canvas Subtitles (R1, R2):
   - Verify unboxed canvas subtitle overlay without teleprompter card wrapping (white `#FFFFFF`, 2px outline, subtle shadow, bottom-centered).
   - Verify visual lanes for Video, Subtitles, Dubbed TTS, and BGM; clickable timeline/ruler seeking; interactive playhead needle spanning all tracks; cue selection.
4. Audio Separation & BGM (R3):
   - Independent 0–150% volume sliders and mute toggles for original, dubbed TTS, and BGM.
   - BGM upload, replace, remove, and sync playback with `<audio id="stage4-bgm-preview">`.
5. Video Thumbnail Management (R5):
   - Upload/replace thumbnail with aspect-video preview card (`[data-thumbnail-preview]`); reset to default first frame.
6. Backend Route & Export Resilience (webui.py):
   - Ensure `/api/assets/{kind}` and `/api/jobs` (with `jobType: "render"`) correctly handle mix levels, BGM ID, thumbnail ID, and edited SRT.
   - Add ergonomic route aliases `/api/render` and `/api/export` mapped to `create_job_handler` so export requests work seamlessly whether called via `/api/jobs`, `/api/render`, or `/api/export`.

Verification:
- Run `uv run pytest` to ensure existing and Stage 4 tests pass without regressions.
- Document all changes in `c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_worker_s4\changes.md`.
- Write `c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_worker_s4\handoff.md` with: Observation, Logic Chain, Caveats, Conclusion, Verification Method.
- Send a completion message to your parent.
