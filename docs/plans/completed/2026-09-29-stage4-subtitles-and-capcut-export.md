# Execution Plan: Stage 4 Subtitle Customization, Embedded Video Render & CapCut Export Package

Date: 2026-09-29

## Status

Completed

## Outcome

1. **Stage 4 In-Editor Subtitle Customization**:
   - Subtitles inspector tab supports Font Size (12px to 64px), Font Family dropdown (Arial, Inter, Impact, Roboto, Georgia, System Default), Font Style toggles (Bold, Italic), and Opacity / Transparency slider (0% to 100%).
   - Live canvas preview in `VideoPlayer.tsx` immediately reflects font size, font family, bold, italic, and opacity in real-time.
   - Complete video render passes styled subtitle settings to the backend to generate burned-in hard subtitles with matching font typography and alpha transparency via ASS (`_srt_ass.py`).

2. **CapCut 4-Asset Export Package**:
   - Users can export the 4 canonical editing assets:
     - `subtitles_edited.srt` (user-edited subtitles)
     - `subtitles_target.srt` (raw target-language translated subtitles)
     - `video.mp4` (video file)
     - `voiceover_merged.wav` (final merged audio track containing all voice segments)
   - Available both as individual file downloads and as a "Download All as ZIP" archive.

3. **"Continue in CapCut" Button & Workflow Modal**:
   - In `StatusFooter.tsx` (active during Stage 4), add a dedicated "Continue in CapCut" button adjacent to "Render dubbed video".
   - Hovering over the button displays a tooltip guide:
     *"Export your video, merged audio, and .srt subtitles, then import them directly into CapCut for advanced effects and transitions."*
   - Clicking opens the **CapCut Export Modal**:
     - Step-by-step import instructions.
     - 4 asset download cards + "Download All as ZIP".
     - Launcher buttons: "Open Folder in Explorer" and "Launch CapCut" (`capcut://` with fallback to CapCut Web).

## Context

- `AGENTS.md`: Repository authority and bounds.
- `.agents/ORIGINAL_REQUEST.md`: Specifications and acceptance criteria.
- User decisions (Q1-A, Q2-A, Q3-A, Q4-A).
- Frontend files: `frontend/src/types/editor.ts`, `frontend/src/store/editVideoSlice.ts`, `frontend/src/screens/Stage4EditVideo.tsx`, `frontend/src/components/VideoPlayer.tsx`, `frontend/src/components/StatusFooter.tsx`, `frontend/src/components/CapCutExportModal.tsx`.
- Backend files: `videotrans/util/_srt_ass.py`, `videotrans/api/task_params.py`, `videotrans/api/routes/projects.py`.

## Scope

In scope:
- Extend `SubtitleStyleSettings` and `subtitleStyles` state in frontend with `fontFamily`, `fontWeight`, `fontStyle`, and `opacity`.
- Add Font Family dropdown, Bold and Italic toggles, and Opacity slider to `Stage4EditVideo.tsx`.
- Update `VideoPlayer.tsx` preview styling to apply font family, font weight, font style, and opacity.
- Update `videotrans/util/_srt_ass.py` to parse `fontWeight`, `fontStyle`, and `opacity` (alpha channel `&HAABBGGRR&`).
- Add CapCut Export Modal component `CapCutExportModal.tsx` and integrate it into `Stage4EditVideo` and `App.tsx`.
- Add "Continue in CapCut" button with tooltip in `StatusFooter.tsx` (visible in Stage 4).
- Add CapCut 4-asset export generation (SRT files generation, audio merge, and zip packaging) with backend endpoints and frontend client integration.
- Automated tests covering backend ASS parsing, subtitle customization, CapCut button presence, tooltip, and export modal interactions.

Out of scope:
- Re-architecting ASR or Translation engines in Stages 1 & 2.
- Replacing FFmpeg or external ASS renderers.

## Progress

- [x] Settle product policy decisions with user via `/grill-me` (Q1-A, Q2-A, Q3-A, Q4-A).
- [x] Implement backend `_srt_ass.py` typography parsing (weight, italic, opacity alpha) and write backend tests.
- [x] Add backend endpoints in `videotrans/api/routes/projects.py` for CapCut 4-asset bundle and merged audio.
- [x] Update frontend types (`editor.ts`), slice (`editVideoSlice.ts`), and render payload builder (`buildRenderRequest`).
- [x] Update `VideoPlayer.tsx` subtitle styling for live canvas preview.
- [x] Implement subtitle controls in `Stage4EditVideo.tsx` (Font family, Bold/Italic toggles, Opacity slider).
- [x] Build `CapCutExportModal.tsx` and add "Continue in CapCut" button with tooltip in `StatusFooter.tsx`.
- [x] Author automated tests in `frontend/tests/capcutExport.test.tsx` and `tests/test_stage4_edit_video.py`.
- [x] Run full test suites (`bun test`, `bun run build`, `uv run pytest`).

## Validation

- Focused proof:
  - `uv run pytest tests/test_stage4_edit_video.py` passed (28 passed).
  - `bun test` in `frontend/` passed (117 passed across 7 test files).
- Integration / build proof:
  - `cd frontend && bun run build` passed cleanly with 0 TypeScript/build errors.
  - Multi-suite pytest: `uv run pytest tests/test_stage4_edit_video.py tests/test_stage3_voice_dubbing.py` passed (53 passed).

## Result

Completed all requirements with verified behavioral and integration proofs. No regressions observed across existing test suites.
