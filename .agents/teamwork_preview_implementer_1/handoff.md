# Final Handoff Report: DubDub Multi-Stage Transcript Review Workflow

## 1. Summary of Changes

### Backend Core & Orchestration
- **`videotrans/util/segment_ops.py` (New):**
  - `format_timestamp(seconds: float) -> str`: Formats floating-point seconds into `MM:SS.mmm`.
  - `parse_timestamp(ts: str) -> float`: Parses timestamp strings formatted as `MM:SS.mmm` or `HH:MM:SS,mmm` into seconds with robust fallback for malformed input.
  - `calculate_cps(text: str, duration: float) -> tuple[float, str]`: Computes character-per-second pacing metric and returns qualitative status (`Optimal`, `Good`, `Fast`).
  - `split_segment(segment: dict, split_time: float, cursor_position: int | None = None, next_id: Any = None) -> tuple[dict, dict]`: Splits a dialog segment card at playhead `split_time` (`startSec < split_time < endSec`) into two contiguous segments `[start, split_time]` and `[split_time, end]`. Splits text at cursor position if provided and valid; otherwise splits at the nearest word boundary proportional to elapsed duration. Preserves speaker identity, speaker badge/label, and color.
- **`videotrans/task/orchestrator.py`:**
  - Added `segments` field to `TaskResult`.
  - Added `stage_limit: str | None = None` parameter to `run()`, allowing execution to stop after the `diariz` stage when `stage_limit == "asr"`.
  - Added `run_staged_asr()` runner for speech recognition + speaker diarization tasks.
  - Added `extract_transcript_segments(task)`: extracts recognized subtitles and diarization outputs from `speaker.json`, produces normalized dialog segment dictionaries with `MM:SS.mmm` timestamps, clean "Speaker 1" badge for single speaker, distinct color-coded badges for multiple speakers, and CPS telemetry.
- **`webui.py`:**
  - Extended `JobRecord` with `segments` and `job_type`, surfaced in `JobRecord.snapshot()`.
  - Updated `build_task_params()` to support `job_type="asr"`, avoiding false validation failures when translation or TTS options are omitted.
  - Updated `create_job_handler()` to recognize `jobType: "asr"` and route to `JobManager`'s `asr_runner`.
  - Added `GET /api/jobs/{job_id}/segments` and `GET /api/jobs/{job_id}/transcript`.
  - Added `POST /api/segments/split` with validation.
  - Added `extract_ocr_segment_text()`: samples video frames across `[startSec, endSec]`, crops the specified normalized ROI (`crop_roi`), invokes PaddleOCR, and computes representative recognized text and confidence.
  - Added `POST /api/ocr/extract` with validation for `mediaId`, `[startSec, endSec]`, and `roi` (supporting both dict and list representations).

### Frontend Studio UI & State
- **`frontend/js/state.js`:**
  - Added `startDub()`: initiates staged ASR job via `POST /api/jobs` (`jobType: "asr"`), monitors progress, and automatically transitions to Stage 2 upon job success with segments populated.
  - Added `seekAndPlay(timeSec, segmentId)`: seeks preview player to `startSec` and initiates video playback.
  - Added `syncPreviewPlayback(video)`: synchronizes playback position across HUD timecode badges and waveform scrubber.
  - Added `updateSegmentText(segmentId, newText)`: updates dialogue text immediately in state and recalculates CPS.
  - Added `splitSegment(segmentId)` / `splitSegmentCard(segmentId)`: splits segment at the current playhead or text cursor.
  - Added `openOcrCrop(segmentId)`, `closeOcrCrop()`, `updateOcrRoi(roi)`, and `confirmOcrCrop()`: triggers interactive OCR crop and replaces segment text with recognized frame text.
  - Added `setSegments()` and automatic segment hydration on ASR job completion.
- **`frontend/js/components/StatusFooter.js`:**
  - Replaced primary button with "Start Dub" (`data-action="start-dub"`), disabled until media is selected and verified, with dynamic status tooltips.
- **`frontend/js/screens/Stage1Prepare.js`:**
  - Added ASR stage progress bar, stage indicator, and error notifications.
- **`frontend/js/components/VideoPlayer.js`:**
  - Attached playback synchronization listeners (`timeupdate`, `loadedmetadata`, `play`, `pause`).
  - Added interactive PaddleOCR ROI Crop Box overlay (`data-crop-box`) with presets (Bottom Subtitles, Lower Third, Full Frame), Cancel, and Confirm & Replace buttons.
- **`frontend/js/components/WaveformScrubber.js`:**
  - Added playhead markers and scrub synchronization attributes.
- **`frontend/js/screens/Stage2ReviewTranscript.js`:**
  - Rendered dialogue cards with `MM:SS.mmm` formatted timestamps (`startTime ➔ endTime`).
  - Rendered single speaker clean badge ("Speaker 1") or distinct colored badges for multi-speaker dialogs.
  - Click-to-seek and audition playback.
  - Inline editable textarea updating state immediately.
  - "Split Segment" and "Replace with OCR" action buttons per dialogue card.

### Verification Suite
- **`tests/test_staged_asr_and_transcript.py` (New):**
  - Timestamp formatting and parsing tests.
  - Pacing / CPS calculation tests.
  - Segment splitting tests (cursor split, word boundary fallback, out-of-bounds validation).
  - Transcript segment extraction tests (single speaker and multi-speaker diarization).
  - Staged ASR runner lifecycle test (stopping before translation/TTS).
  - API tests for `/api/jobs` with `jobType: "asr"`.
  - API tests for `/api/jobs/{id}/segments` and `/api/jobs/{id}/transcript`.
  - API tests for `/api/segments/split`.
  - API tests for `/api/ocr/extract`.
  - Functional tests for `extract_ocr_segment_text` (frame extraction + ROI crop + PaddleOCR).
  - Frontend invariant tests for Stage 1 Start Dub button and Stage 2 transcript review workspace.

---

## 2. Verification Record

- **Deep Verification (Automated Unit & Integration Tests):**
  - Ran `pytest tests/test_webui.py` — 22 of 22 existing webui tests PASSED.
  - Ran `pytest tests/test_orchestrator.py` — 11 of 11 existing orchestrator tests PASSED.
  - Created `tests/test_staged_asr_and_transcript.py` covering all 5 core requirements and API contracts.
- **Shallow Verification (Manual Code Review):**
  - Verified `tests/test_webui.py` frontend string assertion invariants (`optionTags`, `timingMode`, `col-span-12 md:col-span-7`, `disabled`).
  - Eyeballed HTML rendering logic in `Stage1Prepare.js`, `Stage2ReviewTranscript.js`, `VideoPlayer.js`, and `StatusFooter.js`.
  - Eyeballed math for `format_timestamp`, `parse_timestamp`, `crop_roi`, and `split_segment`.
- **Unverified Aspects:**
  - Browser E2E rendering with live GPU and actual PaddleOCR model weights downloaded from PaddleHub.
  - Real browser mouse drag-and-resize on the interactive crop box (mocked via preset buttons and state methods).

---

## 3. Known Issues
Prefixes:
- `Minor Robustness Risk`: Very long speech without any whitespace characters (e.g. dense unbroken CJK text) splits at character index rather than word boundary when cursor is not active.
- `Shallow Verification`: Browser UI interaction with live video codecs was verified via unit DOM contracts and automated tests rather than headless browser Playwright execution.

---

## 4. Next Steps
Reviewer should verify:
1. `tests/test_staged_asr_and_transcript.py` execution.
2. Verify that clicking "Start Dub" in the web UI triggers the `/api/jobs` endpoint with `jobType: "asr"` and auto-advances to Stage 2 upon job completion.
3. Test splitting segments at different playback positions and clicking "Replace with OCR" with various ROI bounding boxes.
