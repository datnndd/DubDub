# Automated Verification Test Suite Ready — Stage 4: Edit Video (Iteration 2 Remediation)

## Milestone
**Milestone**: M3 — Stage 4 E2E Automated Verification & Adversarial Gate (Remediated)  
**Target File**: `tests/test_stage4_edit_video.py`  
**Framework**: `pytest` + `aiohttp.test_utils` + Headless Node.js (ES Module evaluation)  
**Execution Command**: `uv run pytest tests/test_stage4_edit_video.py -v`

---

## Test Inventory Summary Across Tiers 1–4

| Tier | Category / Scope | Test Cases | Status |
|---|---|---|---|
| **Tier 1** | **Backend API Endpoints & Asset Ingestion** (`/api/assets/{kind}`, `/api/jobs`, route aliases) | 10 tests (15 parameterized cases) | VERIFIED & REMEDIATED |
| **Tier 1** | **Task Configuration & Render Parameters** (`build_task_params`, ASS conversion) | 3 tests (7 parameterized cases) | VERIFIED & REMEDIATED |
| **Tier 2** | **Store State Logic & Boundary Clamping** (audio mix 0–150%, mute toggles, timing boundaries, SRT format) | 6 tests | VERIFIED & REMEDIATED (Node.js live) |
| **Tier 1/2** | **Frontend DOM Contracts & Structural Invariants** (3-area studio, unboxed canvas subtitle, multi-track timeline, inspector controls) | 7 tests (8 parameterized cases) | VERIFIED & REMEDIATED |
| **Tier 3** | **Headless Node.js ES Module Evaluation** (`Stage4EditVideo.js` multi-tab rendering & `state.js` mutations) | 2 tests | VERIFIED & REMEDIATED (Node.js live) |
| **Tier 4** | **End-to-End Workflow & Adversarial Stress Tests** (full studio session, zero/single cues, corrupted timing, Unicode diacritics) | 4 tests | VERIFIED & REMEDIATED (Node.js live) |
| **Total** | **Comprehensive Stage 4 Verification Suite** | **32 test functions (42 executable test cases)** | **READY (100% PASS)** |

---

## Remediation Summary (Iteration 2)

1. **Import Resolution (`tests/test_stage4_edit_video.py:72`)**:
   - Replaced invalid import from `videotrans.task.job` with canonical import from `videotrans.task.orchestrator` (`CancellationToken, EventKind, TaskEvent, TaskRequest, TaskResult, TaskStatus`).
2. **Test Double Signature Conformity (`dummy_job_runner`, lines 94-118)**:
   - Updated `accept` callback to emit structured `TaskEvent` instance matching `JobRecord.accept(self, event: TaskEvent)`.
   - Initialized `TaskResult` with all required positional arguments (`job_id`, `status`, `output_dir`, `outputs`).
3. **Multi-Tab Headless Screen Rendering (`test_headless_node_stage4_screen_render`, lines 923-990)**:
   - Sequentially renders across all 3 inspector tabs (`subtitles`, `audio`, `thumbnail`) to assert tab-specific controls on active panels while verifying shared canvas, playhead, and multi-track timeline elements across all outputs.
4. **Replacement of Self-Certifying Mock Tests (Section 3 & Section 6)**:
   - Replaced local mock Python functions (`clamp_mix`, `toggle_mute`, `update_timing`, `serialize_srt`, `serialize`) with genuine Node.js execution against `frontend/js/state.js` (`store.updateAudioMix`, `store.toggleAudioMute`, `store.updateStage4Timing`, `store.serializeEditedSrt`, `store.removeBackgroundAudio`, `store.removeThumbnail`) and `frontend/js/screens/Stage4EditVideo.js`.
5. **Backend Safe Volume Parsing (`webui.py:_safe_volume`, lines 348-360)**:
   - Added `_safe_volume` with boundary clamping `[0.0, 1.5]`, NaN/None rejection, and default fallbacks (`0.8` for `backgroundAudioVolume`, `0.0` for `originalAudioVolume`).
   - Added overflow protection for dubbed `volume` float diff rounding.
6. **Backend Asset Ingestion & Route Isolation (`webui.py:edit_asset_handler`, lines 800-845)**:
   - Rejects `application/x-www-form-urlencoded` submissions without files with HTTP 400 Bad Request.
   - Enforces `X-Filename` header / query parameter for raw binary uploads.
   - Enforces non-zero byte size (`st_size > 0`) and unlinks empty files with HTTP 400.
   - Uses `request.app["media_store"].upload_dir` for proper filesystem encapsulation.
7. **ASR Bypass for Render Tasks (`webui.py:create_job_handler`, lines 855-885)**:
   - Bypasses `ensure_asr_configured` when `job_type == "render"`.
   - Expanded exception catching for `(ValueError, TypeError, OverflowError)` to return clean HTTP 400 Bad Request responses.

---

## Detailed Test Mapping by Section

### Section 1: Backend API Endpoints & Asset Ingestion
- `test_asset_upload_background_audio_multipart_success`: Multipart upload of audio files (`.mp3`, `.wav`) returning 201, UUID id, and registered file path in `EDIT_ASSETS`.
- `test_asset_upload_thumbnail_multipart_success`: Multipart upload of image files (`.webp`, `.png`, `.jpg`) returning 201 and registering in `EDIT_ASSETS`.
- `test_asset_upload_raw_binary_with_x_filename`: Raw binary upload with `X-Filename` header support returning 201.
- `test_asset_upload_rejects_unsupported_kinds`: Rejecting unknown asset kinds (e.g. `/api/assets/video`) with HTTP 404.
- `test_asset_upload_rejects_invalid_extension`: Rejecting executable/script files (`.exe`, `.sh`, `.txt`, `.pdf`, `.gif`) with HTTP 400.
- `test_asset_upload_requires_file_or_content`: Rejecting missing file part, empty payloads, or x-www-form-urlencoded payloads with HTTP 400.
- `test_create_render_job_resolves_asset_ids`: Submitting `jobType="render"` resolving `backgroundAudioId` and `thumbnailId` to disk paths.
- `test_create_render_job_rejects_missing_asset_id`: Error handling with HTTP 400 when asset IDs are invalid or expired.
- `test_create_render_job_bypasses_translation_config_check`: Verifying render tasks bypass ASR/translation configuration checks.
- `test_api_render_and_export_aliases`: Verifying ergonomic route aliases `POST /api/render` and `POST /api/export`.

### Section 2: Task Configuration & Render Parameters
- `test_render_params_reuse_edited_srt_and_mix_settings`: Parameter mapping for render jobs (`source_audio_volume`, `backaudio_volume`, `volume`, `background_music`, `thumbnail`, `clear_cache=False`).
- `test_build_task_params_volume_boundary_clamping`: Clamping `source_audio_volume` and `backaudio_volume` strictly between `0.0` and `1.5`.
- `test_build_task_params_subtitle_style_and_ass_conversion_compatibility`: Compatibility with `set_ass_font` and ASS BGR colour conversion.

### Section 3: Store State Logic & Boundaries (Live Node.js Execution)
- `test_audio_mix_clamping_0_to_150`: Live `store.updateAudioMix` clamping slider levels strictly between `0%` and `150%`.
- `test_audio_mute_toggle_saves_and_restores_previous_mix`: Live `store.toggleAudioMute` caching active levels in `prevMix` upon muting and restoring on unmute.
- `test_update_stage4_timing_bounds_and_adjacent_constraints`: Live `store.updateStage4Timing` enforcing `startSec < endSec` and adjacent segment boundaries (`seg[k].startSec >= seg[k-1].endSec`).
- `test_serialize_edited_srt_formatting_and_indexing`: Live `store.serializeEditedSrt` producing valid standard SRT blocks with 1-based indexing and comma-separated millisecond timecodes.
- `test_thumbnail_and_bgm_lifecycle_and_cleanup`: Live `store.removeBackgroundAudio` and `store.removeThumbnail` resetting state and revoking blob URLs.
- `test_stage4_inspector_tabs`: Inspector tab switching (`audio`, `subtitles`, `thumbnail`) in screen and state.

### Section 4: Frontend DOM Contracts & Invariants
- `test_stage4_frontend_uses_shared_segments_and_connected_render_action`: Shared segment mapping and footer render trigger.
- `test_stage4_three_area_layout_structure`: Widescreen preview, contextual inspector, and lower timeline layout decks.
- `test_stage4_capcut_timeline_and_track_elements`: Visual tracks for Video, Subtitles, Dubbed TTS, and BGM with playhead needle.
- `test_stage4_audio_sources_and_bgm_sync`: Audio mix sliders, mute toggles, and BGM synchronization elements.
- `test_stage4_subtitle_styling_and_font_size_controls`: Subtitle font size dynamic controls, default clean styling (`#FFFFFF`, 2px outline, shadow).
- `test_stage4_thumbnail_management`: Thumbnail upload dropzone and aspect-video preview card.
- `test_edit_asset_rejects_unsupported_extensions`: Static extension validation.

### Section 5: Headless Node.js ES Module Evaluation
- `test_headless_node_stage4_screen_render`: Executing `renderStage4EditVideo` across all 3 inspector tabs (`subtitles`, `audio`, `thumbnail`) in Node.js and asserting compiled DOM elements.
- `test_headless_node_stage4_state_and_srt_workflow`: Executing state mutations and SRT serialization directly in Node.js.

### Section 6: End-to-End Workflow & Adversarial Stress Tests
- `test_e2e_stage4_edit_and_render_export_scenario`: Complete simulated user session from asset upload to render export.
- `test_adversarial_zero_and_single_segment_timeline_math`: Live Node.js test verifying 0 and 1 segment handling and division-by-zero resilience.
- `test_adversarial_corrupted_or_extreme_srt_timing`: Multi-line text, non-ASCII Unicode (Vietnamese diacritics, Chinese characters, emojis), and XML character resilience.
- `test_adversarial_invalid_audio_mix_inputs`: Handling of `None`, non-numeric strings, and extreme numbers in audio volume inputs.

---

## Verification Instructions

Run the test suite with:
```bash
uv run pytest tests/test_stage4_edit_video.py -v
uv run pytest tests/test_stage3_voice_dubbing.py tests/test_webui.py -v
```
