# Execution Plan: Stage 2 Subtitle OCR Replacement & UI Simplification

Date: 2026-10-02

## Status

Completed

## Outcome

Allow users in Stage 2 to replace an inaccurate ASR-generated transcription segment with PaddleOCR-extracted subtitles from the original video within that segment's exact time range.
The system will:
1. Scan the video strictly within `[startSec, endSec]` using PaddleOCR and the user's defined ROI.
2. Produce 1 or more valid SRT entries for any subtitles appearing and changing within that window.
3. Directly replace the single ASR segment with the newly generated OCR subtitle entries in the timeline.
4. Auto-update the timeline, renumber segments, preserve speaker attribution, and clear `targetText` for re-translation.
5. Reorganize and simplify the Stage 2 interface: remove intrusive permanent yellow banners and clutter, add clear transcription source badges (`ASR` vs `OCR`), and provide an intuitive modal review & replace workflow.

## Context

- `AGENTS.md` & `docs/WORKFLOW.md`: Durable plan in `docs/plans/active/`, repository as system of record, verified proof before completion.
- `docs/decisions/0001-video-ocr-as-subtitle-source.md`: Hard-subtitle OCR architecture and PaddleOCR provider boundary.
- `videotrans/api/ocr_helpers.py`: OCR extraction helpers for WebUI.
- `videotrans/api/routes/stages.py`: `/api/ocr/extract` endpoint.
- `videotrans/ocr/`: `OcrScanner`, `SegmentBuilder`, `frame_at`, `sampled_frame_iter`, `PADDLE_OCR`.
- `frontend/src/screens/Stage2ReviewTranscript.tsx`: Stage 2 transcript review screen.
- `frontend/src/components/Stage2OcrDialog.tsx`: OCR inspection dialog.
- `frontend/src/store/transcriptSlice.ts`: Segments store and state mutations.
- `frontend/src/types/segment.ts`: Segment data contract.

## Scope

In scope:
- Backend: Interval-based OCR subtitle extraction producing 1..N SRT entries (`entries: list[dict]`) with timestamps and confidence.
- Store: `replaceSegmentWithOcrEntries` action in `transcriptSlice` supporting 1-to-N segment replacement, speaker inheritance, `sourceType: 'ocr'`, timeline sorting, ID re-indexing, and autosave.
- UI: Simplified, decluttered Stage 2 screen with `ASR` and `OCR` source indicators on cards, removal of the permanent yellow bulk-select banner.
- Modal: Review & Replace OCR dialog showing video frame, ROI bounding box, scan button, preview of detected SRT subtitle entries, and confirmation action.
- Unit & integration tests for backend interval scanning, store replacement logic, and UI rendering.

Out of scope:
- Full-video whole-stream OCR overhaul (handled in Stage 1 / CLI).
- Non-Paddle OCR providers (PaddleOCR remains the local engine).

## Approach

1. **Backend Interval OCR & SRT Generator (`videotrans/api/ocr_helpers.py`, `videotrans/api/routes/stages.py`)**:
   - Enhance `extract_ocr_segment_text` to stream samples across `[start_sec, end_sec)` using `SegmentBuilder`.
   - Produce a list of `entries` with `startSec`, `endSec`, `startTime`, `endTime`, `text`, `confidence`.
   - Ensure backward compatibility on `/api/ocr/extract`.
   - Add unit tests in `tests/test_ocr_stage2_repair.py`.

2. **Frontend Store & Data Contracts (`frontend/src/types/segment.ts`, `frontend/src/store/transcriptSlice.ts`)**:
   - Update `Segment` interface to include `sourceType?: 'asr' | 'ocr'`.
   - Implement `replaceSegmentWithOcrEntries(segmentId, ocrEntries)`:
     - Replace the single segment with the new N entries.
     - Inherit `speakerId`, `speakerName`, `speakerColor`.
     - Set `sourceType: 'ocr'`, `sourceText: entry.text`, `targetText: ''`.
     - Sort segments by `startSec`, re-index sequential IDs.
     - Trigger autosave.

3. **Stage 2 UI Reorganization (`frontend/src/screens/Stage2ReviewTranscript.tsx`, `frontend/src/components/Stage2OcrDialog.tsx`)**:
   - Remove the permanent yellow bulk-OCR banner and clutter.
   - Display a clean `ASR` or `OCR` badge in each segment header.
   - Add a prominent "Replace with OCR" action on each card.
   - Upgrade the OCR dialog: preview video with ROI, scan interval, display the generated OCR subtitle entries, and provide a "Replace Segment" button.
   - Preserve ASR segment and warn if no text detected.

4. **Validation & Proof**:
   - Run Python unit tests (`pytest tests/test_ocr_stage2_repair.py` and `tests/test_ocr_*.py`).
   - Run Frontend tests (`bun test tests/ocrStage2.test.tsx` and full suite).
   - Verify frontend production build (`bun run build`).

## Risks And Recovery

- Risk: Fast or brief subtitles inside short segments may be missed with coarse sampling.
  Mitigation: Use fine sampling interval (200-250ms) for segment-bounded intervals and fine-tuned similarity threshold (0.95).
- Risk: Replaced segments could cause ID collisions or break speaker voice mapping.
  Mitigation: Re-index IDs sequentially and inherit speaker mapping directly from the replaced segment.
- Recovery: If user is unsatisfied with OCR replacement, original segment is preserved until user clicks "Replace Segment", and normal undo/redo or re-ASR is available.

## Progress

- [x] Add backend interval OCR scanning returning structured `entries` list.
- [x] Add backend unit tests for 1..N segment extraction.
- [x] Update frontend `Segment` types and `transcriptSlice` replacement action.
- [x] Overhaul `Stage2OcrDialog` for review & replace workflow.
- [x] Reorganize and declutter `Stage2ReviewTranscript.tsx` with source badges.
- [x] Validate end-to-end with automated test suite and frontend build.

## Decisions

- 2026-10-02: Modal / Drawer workflow with ROI adjustment and preview before confirming replacement.
- 2026-10-02: All new OCR entries inherit speaker attribution from the replaced segment, with `targetText` reset to empty for re-translation.
- 2026-10-02: Preserve ASR segment and warn user if no text is detected in the ROI.
- 2026-10-02: Remove permanent yellow bulk banner and card checkboxes; use card-level source badges ("ASR" / "OCR") and direct "Replace with OCR" action.

## Validation

- Focused proof: `pytest tests/test_ocr_stage2_repair.py` covering 1-to-N subtitle extraction and empty ROI handling (10/10 passed).
- Regression proof: `pytest tests/test_ocr_paddle.py tests/test_ocr_scanner.py tests/test_ocr_stage2_repair.py` (25/25 passed).
- Integration proof: `bun test tests/ocrStage2.test.tsx` (15/15 passed) and full frontend test suite (154/154 passed).
- Build proof: `bun run build` (`tsc && vite build`) built cleanly in 6.23s.

## Result

Successfully completed and validated.
All requirements met:
1. Exact `[startSec, endSec]` video scanning using PaddleOCR and custom ROI.
2. 1-to-N valid SRT subtitle entries extracted when hard subtitles change within the window.
3. Direct in-place replacement of the ASR segment with the OCR entries.
4. Auto-updated timeline with speaker inheritance, sequential ID re-indexing, and autosave.
5. Clean, decluttered Stage 2 UI with clear `ASR` and `OCR` source badges, streamlined toolbar, and an intuitive "Review & Replace" modal.
