# Detailed Changes Report: Stage 4 Redesign Remediation (Iteration 2)

**Author**: `worker_remediate_s4`  
**Date**: 2026-09-20  
**Target Milestone**: Stage 4 Edit Video Redesign Remediation  
**Status**: Completed  

---

## 1. Overview of Modified Files

1. `webui.py` — Backend API handlers and task parameter mapping
2. `tests/test_stage4_edit_video.py` — Automated verification test suite for Stage 4
3. `TEST_READY.md` — Attestation and inventory of automated test readiness

---

## 2. Modifications to `webui.py`

### 2.1 Added `math` Module Import
- **Location**: Line 7
- **Rationale**: Needed for `math.isnan(val)` checking in `_safe_volume`.

### 2.2 Added `_safe_volume` Function
- **Location**: Lines 348–360
- **Implementation**:
  ```python
  def _safe_volume(value: Any, default: float) -> float:
      """Safely coerce volume float value clamped to [0.0, 1.5], with fallback default."""
      if value is None or isinstance(value, bool):
          return default
      try:
          val = float(value)
          if math.isnan(val):
              return default
          return max(0.0, min(1.5, val))
      except (TypeError, ValueError, OverflowError):
          return default
  ```
- **Rationale**: Prevents uncaught `TypeError` on `None`, `ValueError` on non-numeric strings (e.g., `"not-a-number"`), `OverflowError` on extreme numbers, and NaN propagation, defaulting gracefully to caller-specified fallback.

### 2.3 Hardened `build_task_params`
- **Location**: Lines 495–585
- **Changes**:
  1. For `job_type == "render"`, make `recognType` optional, falling back to index `0` and the default model without throwing `ValueError: ASR engine is required`.
  2. In the translation and TTS configuration branch, permit `job_type == "render"` alongside `job_type == "asr"` (`if is_asr_only or job_type == "render":`) to bypass strict translation engine requirements and use safe defaults (`voice_role = str(options.get("voiceRole") or "No")`).
  3. Wrapped `raw_vol` float diff calculation in `try...except (OverflowError, ValueError)` to prevent `OverflowError: cannot convert float infinity to integer`.
  4. Used `_safe_volume` for both volume parameters:
     - `"backaudio_volume": _safe_volume(options.get("backgroundAudioVolume"), 0.8)`
     - `"source_audio_volume": _safe_volume(options.get("originalAudioVolume"), 0.0)`
- **Rationale**: Ensures render requests without ASR/translation options execute cleanly without unhandled crashes.

### 2.4 Hardened `edit_asset_handler`
- **Location**: Lines 800–845
- **Changes**:
  1. Reject requests with `content-type: application/x-www-form-urlencoded` immediately with `web.HTTPBadRequest(text="An asset file is required")`.
  2. For multipart requests, stream uploaded chunks into `store.upload_dir / ...` using `request.app["media_store"]`.
  3. For non-multipart / raw binary requests, require `X-Filename` header or `?filename=` query parameter; do not invent a fallback filename like `asset.mp3`.
  4. Ensure non-empty payload `content = await request.read()`.
  5. Post-write check: if `saved.stat().st_size == 0`, unlink the empty file and raise `web.HTTPBadRequest(text="An asset file is required")`.
  6. Replaced hardcoded `UPLOAD_DIR` with `request.app["media_store"].upload_dir` to ensure test filesystem isolation.
- **Rationale**: Resolves vulnerability where form submissions registered pseudo-assets, empty files corrupted FFmpeg, and global temp directories leaked between tests.

### 2.5 Updated `create_job_handler`
- **Location**: Lines 855–885
- **Changes**:
  1. Only call `ensure_asr_configured` if `job_type != "render"`.
  2. Expanded exception handling from `except ValueError as exc:` to `except (ValueError, TypeError, OverflowError) as exc: raise web.HTTPBadRequest(text=str(exc)) from exc`.
- **Rationale**: Render jobs only mix audio and burn subtitles, requiring no speech recognition credentials (e.g. Deepgram API keys).

---

## 3. Modifications to `tests/test_stage4_edit_video.py`

### 3.1 Fixed Symbol Imports (Line 72)
- **Change**: Imported `CancellationToken, EventKind, TaskEvent, TaskRequest, TaskResult, TaskStatus` from `videotrans.task.orchestrator` instead of `videotrans.task.job`.
- **Rationale**: `videotrans/task/job.py` defines Qt GUI worker threads, whereas `videotrans/task/orchestrator.py` defines the task orchestration engine.

### 3.2 Fixed `dummy_job_runner` Fixture (Lines 94–118)
- **Change**:
  - `accept` now passes a `TaskEvent` instance (`TaskEvent(job_id=str(job_id), kind=EventKind.PROGRESS, stage="render", message="...", progress=50.0)`).
  - `TaskResult` initialized with all required positional parameters: `job_id`, `status=TaskStatus.SUCCEEDED`, `output_dir=output_dir`, `outputs=(Path("output.mp4"),)`.
- **Rationale**: Eliminates background worker thread crashes with `TypeError: JobRecord.accept() takes 2 positional arguments but 3 were given` and missing arguments in `TaskResult`.

### 3.3 Replaced Self-Certifying Mock Tests in Section 3
- **Location**: Lines 614–780
- **Changes**:
  - `test_audio_mix_clamping_0_to_150`: Executes Node.js script invoking `store.updateAudioMix('original', val)` in `frontend/js/state.js`, asserting clamping across `-10`, `0`, `75`, `150`, `200`, and `"invalid"`.
  - `test_audio_mute_toggle_saves_and_restores_previous_mix`: Executes Node.js script invoking `store.toggleAudioMute` on `store` in `frontend/js/state.js`, testing mute caching in `prevMix` and unmute restoration.
  - `test_update_stage4_timing_bounds_and_adjacent_constraints`: Executes Node.js script invoking `store.updateStage4Timing` in `frontend/js/state.js` with sample segments, verifying adjacent constraints and `startSec < endSec`.
  - `test_serialize_edited_srt_formatting_and_indexing`: Executes Node.js script invoking `store.serializeEditedSrt()` in `frontend/js/state.js`, verifying 1-based indexing and standard timestamp formatting.
  - `test_thumbnail_and_bgm_lifecycle_and_cleanup`: Executes Node.js script invoking `store.removeBackgroundAudio()` and `store.removeThumbnail()`, verifying state nullification and `URL.revokeObjectURL` calls.
- **Rationale**: Eliminates self-certifying local Python mock functions (`clamp_mix`, `toggle_mute`, `update_timing`, `serialize_srt`) so tests genuinely verify production frontend JavaScript logic.

### 3.4 Fixed Multi-Tab Headless Screen Rendering in Section 5
- **Location**: Lines 923–990 (`test_headless_node_stage4_screen_render`)
- **Changes**:
  - Sequentially renders each inspector tab (`subtitles`, `audio`, `thumbnail`).
  - Asserts tab-specific elements on the corresponding rendered HTML:
    - `subtitles`: `data-action="update-font-size"`, `data-action="update-font-size-input"`, `data-stage4-subtitle`, `data-segment-input="stage4-1"`
    - `audio`: `data-mix-slider`, `stage4-background-input`, `toggle-mute-original`
    - `thumbnail`: `stage4-thumbnail-input`, `data-thumbnail-preview`
  - Asserts common studio layout and timeline elements on the rendered HTML: `data-stage4-studio`, `#stage4-bgm-preview`, `data-timeline-playhead`, timeline tracks (`video`, `subtitles`, `dubbed`, `bgm`), inspector tab buttons, and export button.
- **Rationale**: Aligns test assertions with the tabbed DOM contract of `Stage4EditVideo.js`.

### 3.5 Replaced Self-Certifying Mock Test in Section 6
- **Location**: Lines 1194–1232 (`test_adversarial_zero_and_single_segment_timeline_math`)
- **Changes**:
  - Executes Node.js script invoking `store.serializeEditedSrt()` and `renderStage4EditVideo(store.state)` on 0 segments and 1 segment, verifying that empty strings and valid single SRT blocks are generated without division-by-zero crashes.
- **Rationale**: Eliminates local `serialize` mock function.

---

## 4. Modifications to `TEST_READY.md`

- Updated with remediation details for Iteration 2.
- Verified test inventory across Tiers 1–4: 32 test functions, 42 executable test cases.
- Recorded status as `VERIFIED & REMEDIATED`.
