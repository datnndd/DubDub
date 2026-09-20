# Implementation Progress: DubDub Multi-Stage Transcript Review Workflow

## Current Status: Completed

### Completed Tasks:
1. **Segment Operations Utility (`videotrans/util/segment_ops.py`):**
   - Implemented `format_timestamp(seconds)` formatting to `MM:SS.mmm`.
   - Implemented `parse_timestamp(ts)` supporting both `MM:SS.mmm` and `HH:MM:SS,mmm` with safe error handling.
   - Implemented `calculate_cps(text, duration)` returning float CPS and qualitative status (`Optimal`, `Good`, `Fast`).
   - Implemented `split_segment(segment, split_time, cursor_position=None, next_id=None)` with contiguous non-overlapping intervals `[start, split_time]` and `[split_time, end]`, text splitting at cursor position if valid, or fallback to the nearest word boundary proportional to duration, preserving speaker attributes and supporting both `sourceText` and `text` properties.

2. **Staged ASR Execution & Extraction (`videotrans/task/orchestrator.py`):**
   - Updated `TaskResult` dataclass to include `segments` tuple.
   - Extended `orchestrator.run()` with `stage_limit: str | None = None` allowing execution limited to `prepare`, `recogn`, and `diariz` stages.
   - Created `run_staged_asr()` runner executing only speech recognition and speaker diarization.
   - Implemented `extract_transcript_segments(task)` to parse source subtitles and speaker diarization metadata (`speaker.json`), generating normalized dialogue cards with `MM:SS.mmm` timestamps, clean single-speaker badge ("Speaker 1") or distinct colored badges for multi-speaker dialogs, and CPS telemetry.

3. **Backend WebUI Endpoints & OCR Runner (`webui.py`):**
   - Updated `JobRecord` with `segments` and `job_type`, surfaced in `snapshot()`.
   - Updated `build_task_params()` to support `job_type="asr"`, bypassing translation/TTS checks.
   - Updated `create_job_handler()` to accept `jobType: "asr"` for staged dubbing preparation.
   - Added `GET /api/jobs/{job_id}/segments` and `GET /api/jobs/{job_id}/transcript` endpoints.
   - Added `POST /api/segments/split` endpoint with boundary validation.
   - Implemented `extract_ocr_segment_text()` taking `media_path`, `[start_sec, end_sec]`, and `roi`, sampling frames across the time window, cropping the ROI via `crop_roi`, running PaddleOCR, and computing representative text.
   - Added `POST /api/ocr/extract` endpoint with media lookup, ROI validation (supporting dict and list), and dependency injection support for `ocr_extractor`.

4. **Frontend Architecture & Components:**
   - **`frontend/js/state.js`:**
     - Added `startDub()` initiating staged ASR job and automatically advancing to Stage 2 upon job success.
     - Added `seekAndPlay(timeSec, segmentId)` for segment playback synchronization.
     - Added `syncPreviewPlayback(video)` synchronizing video time with HUD telemetry and scrubber.
     - Added `updateSegmentText(segmentId, newText)` updating segment text in-store immediately and recalculating CPS.
     - Added `splitSegment(segmentId)` dividing active segment at playhead/cursor.
     - Added `openOcrCrop(segmentId)`, `closeOcrCrop()`, `updateOcrRoi(roi)`, and `confirmOcrCrop()` triggering backend frame OCR extraction and replacing segment text.
   - **`frontend/js/components/StatusFooter.js`:**
     - Replaced primary action button with "Start Dub" at Stage 1, disabled until media is selected & verified, with contextual tooltips and `data-action="start-dub"`.
   - **`frontend/js/screens/Stage1Prepare.js`:**
     - Added live ASR processing progress bar, stage indicator, and error display.
   - **`frontend/js/components/VideoPlayer.js`:**
     - Added video playback synchronization hooks (`data-source-preview`, `data-playhead-timecode`).
     - Added interactive PaddleOCR ROI Crop Box overlay (`data-crop-box`) with presets (Bottom Subtitles, Lower Third, Full Frame), Cancel, and Confirm & Replace buttons.
   - **`frontend/js/screens/Stage2ReviewTranscript.js`:**
     - Rendered recognized transcript as sequential dialogue cards with formatted `MM:SS.mmm` timestamps.
     - Rendered clean "Speaker 1" badge for single speaker and distinct colored badges for multi-speaker.
     - Click-to-seek playback audition.
     - Inline editable textarea with immediate store persistence.
     - "Split Segment" and "Replace with OCR" action buttons per card.

5. **Automated Testing Suite (`tests/test_staged_asr_and_transcript.py`):**
   - Unit tests for `format_timestamp`, `parse_timestamp`, `calculate_cps`.
   - Boundary, cursor, and word-boundary unit tests for `split_segment`.
   - Unit tests for `extract_transcript_segments` (single and multi-speaker) and `run_staged_asr`.
   - API integration tests for `/api/jobs` (`jobType: "asr"`), `/api/jobs/{id}/segments`, `/api/segments/split`, and `/api/ocr/extract`.
   - Functional test for `extract_ocr_segment_text`.
   - DOM and state invariant tests for Stage 1 Start Dub button and Stage 2 transcript review workspace.
