# DubDub AI Video Dubbing Studio — Stage 4: Edit Video
## Automated Verification Strategy & Test Architecture Survey

**Author**: `explorer_survey_tests`  
**Target Milestone**: Stage 4: Edit Video (CapCut-style Lightweight Video Editing Studio)  
**Target Test Suite**: `tests/test_stage4_edit_video.py`  
**Execution Environment**: `uv run pytest` (Python 3.10, PySide6/Torch mocked via `conftest.py`, headless Node.js v22 for optional JS evaluation)

---

### 1. Executive Summary

Stage 4 (*Edit Video*) transforms DubDub from a linear dubbing workflow into an intuitive, lightweight video editing studio inspired by CapCut. The studio enables creators to review dubbed output, balance audio tracks (original audio, synthesized TTS, and background music), customize subtitle typography, tweak subtitle text and cue timings, manage video thumbnails, and trigger the final video rendering pipeline without requiring complex external video editors.

To ensure software reliability, prevent regressions, and enforce requirements R1–R5, this survey establishes a multi-tiered automated verification strategy. The strategy leverages existing repository testing patterns established in Stage 3 (`tests/test_stage3_voice_dubbing.py`), API tests in `tests/test_webui.py`, and mock isolation in `tests/conftest.py`.

---

### 2. Analysis of Existing Test Infrastructure & Patterns

#### 2.1 Repository Test Environment (`pyproject.toml` & `conftest.py`)
- **Python Version**: `>=3.10, <3.11`.
- **Test Runner**: `pytest` under `[dependency-groups] dev`. Executed via `uv run pytest`.
- **Dependency Isolation**: `tests/conftest.py` inspects importability and supplies robust mocks for heavy C++/GPU/API dependencies (`PySide6`, `torch`, `requests`, `tenacity`, `openai`, `deepgram`, `elevenlabs`, `aiohttp`, `httpx`, `pydub`, `ten_vad`). This allows the entire test suite to execute fast (< 2 seconds per test file), headlessly, without requiring GPU hardware, network access, or GUI displays.

#### 2.2 Stage 3 Testing Blueprint (`tests/test_stage3_voice_dubbing.py`)
Stage 3 demonstrated a standard for comprehensive stage verification consisting of 5 distinct sections:
1. **Backend Endpoint Verification**: Utilizing `aiohttp.test_utils.TestClient` and `TestServer` against `webui.create_app()`. Mocks internal catalog functions using `monkeypatch`.
2. **State & Store Logic Verification**: Validates state manipulation specifications (speaker matrices, voice resolution, overrides, text updates) using deterministic test fixtures.
3. **Frontend Component Contracts & DOM Invariants**: Reads frontend JS files (`Stage3VoiceDubbing.js`, `VideoPlayer.js`) and asserts structural contracts (`data-*` attributes, class bindings, template variables).
4. **Component Overlay & Synchronization**: Confirms playback synchronizers and canvas overlay attributes.
5. **Headless Node.js Execution & E2E Scenarios**: Uses `shutil.which("node")` with `subprocess.run` to evaluate actual ES modules (`Stage3VoiceDubbing.js`, `state.js`) in Node.js when available, skipping cleanly if absent.

#### 2.3 Existing Stage 4 Baseline (`tests/test_stage4_edit_video.py`)
The existing file contains 8 foundational tests (147 lines) verifying:
- `test_render_params_reuse_edited_srt_and_mix_settings`: Task configuration parameter mapping for `job_type="render"`.
- `test_stage4_frontend_uses_shared_segments_and_connected_render_action`: String contracts in frontend files.
- `test_stage4_capcut_timeline_and_track_elements`: Presence of timeline lanes and playhead needle.
- `test_stage4_audio_sources_and_bgm_sync`: Audio mix slider markers and BGM sync tags.
- `test_stage4_subtitle_styling_and_font_size_controls`: Subtitle font size controls and CapCut subtitle variant.
- `test_stage4_thumbnail_management`: Thumbnail upload and removal attributes.
- `test_stage4_inspector_tabs`: Tab navigation contract.
- `test_edit_asset_rejects_unsupported_extensions`: Parameterized rejection of invalid asset extensions.

**Identified Gaps to Close**:
1. Live HTTP testing of `/api/assets/{kind}` (uploading audio/image payloads, asserting 201 response, UUID assignment, temporary storage).
2. Live HTTP testing of `POST /api/jobs` with `jobType: "render"`, asset resolution (`backgroundAudioId` -> `backgroundMusicPath`, `thumbnailId` -> `thumbnailPath`), and error handling for missing assets.
3. Rigorous validation of state logic: audio mix clamping (0–150%), toggle mute state caching (`prevMix`), timestamp clamping and ordering during segment editing, and accurate SRT string formatting.
4. Headless Node.js execution of `Stage4EditVideo.js` and `state.js` to execute real DOM template compilation and store mutations.
5. Boundary and adversarial stress testing (empty transcripts, single segment transcripts, extreme audio slider values, malformed SRT).

---

### 3. Stage 4 Acceptance Criteria & Verification Mapping

| Requirement | Acceptance Criteria | Target Verification Mechanism |
|---|---|---|
| **R1. Studio Layout & Video Preview** | 3-area layout (widescreen preview top-left, inspector top-right, timeline bottom). Subtitles rendered directly over canvas without teleprompter card wrapping in clean default style (white `#FFFFFF`, 2px black outline, 2px shadow). Synchronized preview of active audio sources. | DOM contract tests on `Stage4EditVideo.js` & `VideoPlayer.js` (`subtitleVariant === 'capcut'`, `<style>[data-canvas-subtitle]`). Synchronized audio playback assertions in `state.js` (`syncPreviewPlayback`). |
| **R2. Multi-Track Timeline** | Visual lanes for Video, Subtitles, Dubbed TTS, and BGM. Playhead seek on timeline click. Clicking subtitle cue seeks to `startSec`, highlights cue, and activates inspector subtitle editor. Interactive playhead needle across all tracks. | Contract & Node.js DOM tests on `data-timeline-playhead`, `data-segment-card`, track headers, time ruler, and click handlers (`seekAndPlay`, `setStage4InspectorTab`). |
| **R3. Audio Separation & BGM Control** | Independent volume sliders (0–150%) and mute toggles for Original, Dubbed, and BGM. Upload/replace/remove BGM (`audio/*`) with synchronized playback (`#stage4-bgm-preview`). Render request payload passes mix levels (`source_audio_volume`, `backaudio_volume`, `volume`) and `backgroundAudioId`. | Backend API tests on `/api/assets/background-audio`, `build_task_params` mix mapping, volume clamping tests (0–1.5), mute toggle state tests (`prevMix`), and live `POST /api/jobs` submission. |
| **R4. Subtitle Typography & Font Sizing** | Dynamic font size adjustment (slider 14–48px) updating canvas immediately. Default style contract (white text, black outline, subtle shadow). Inline editing of active subtitle text and timecodes (`updateStage4Timing`), immediately updating `state.segments` and export SRT. | State logic tests on `updateStage4Subtitle`, `updateStage4Timing`, `serializeEditedSrt`. Parameter mapping in `build_task_params["subtitle_style"]`. |
| **R5. Thumbnail Management** | Upload/replace video thumbnail (PNG, JPG, WEBP) with aspect-video preview card in inspector. Reset thumbnail to default first frame. Export payload links `thumbnailId`. | Backend API tests on `/api/assets/thumbnail`, state tests on `selectThumbnail`, `removeThumbnail`, and `build_task_params["thumbnail"]`. |

---

### 4. Proposed Test Architecture for `tests/test_stage4_edit_video.py`

The test suite will be structured into 6 comprehensive, modular sections:

```
tests/test_stage4_edit_video.py
├── Section 1: Backend API Endpoints & Asset Upload Tests
│   ├── test_asset_upload_background_audio_success
│   ├── test_asset_upload_thumbnail_success
│   ├── test_asset_upload_rejects_unsupported_kinds
│   ├── test_asset_upload_rejects_invalid_extension
│   ├── test_asset_upload_requires_file
│   ├── test_create_render_job_resolves_asset_ids
│   ├── test_create_render_job_rejects_missing_asset_id
│   └── test_create_render_job_bypasses_translation_config_check
├── Section 2: Task Configuration & Render Parameter Mapping
│   ├── test_build_task_params_render_mix_and_srt
│   ├── test_build_task_params_volume_boundary_clamping
│   └── test_build_task_params_preserves_cache_on_render
├── Section 3: Pure State & Store Logic Tests
│   ├── test_audio_mix_clamping_0_to_150
│   ├── test_audio_mute_toggle_saves_and_restores_previous_mix
│   ├── test_subtitle_font_size_and_style_updates
│   ├── test_update_stage4_timing_bounds_and_adjacent_constraints
│   ├── test_serialize_edited_srt_formatting_and_indexing
│   ├── test_thumbnail_and_bgm_lifecycle_and_cleanup
│   └── test_inspector_tab_state_transitions
├── Section 4: Frontend Component Contracts & DOM Invariants
│   ├── test_stage4_three_area_layout_structure
│   ├── test_stage4_capcut_subtitle_variant_contract
│   ├── test_stage4_multi_track_timeline_lanes_and_playhead
│   ├── test_stage4_audio_mix_sliders_and_mute_buttons
│   ├── test_stage4_subtitle_typography_controls
│   └── test_stage4_thumbnail_inspector_controls
├── Section 5: Headless Node.js Execution (ES Module Evaluation)
│   ├── test_headless_node_stage4_screen_render
│   └── test_headless_node_stage4_state_and_srt_workflow
└── Section 6: End-to-End Workflow & Adversarial Stress Tests
    ├── test_e2e_stage4_edit_and_render_export_scenario
    ├── test_adversarial_zero_and_single_segment_timeline_math
    └── test_adversarial_corrupted_or_extreme_srt_timing
```

---

### 5. Detailed Test Specifications by Tier

#### Tier 1: Feature & Contract Coverage
- **Backend Asset Ingest (`/api/assets/{kind}`)**:
  - Test valid multipart uploads of audio (`.mp3`, `.wav`, `.m4a`) to `/api/assets/background-audio`. Assert HTTP 201, valid UUID `id`, and original filename.
  - Test valid multipart uploads of thumbnails (`.png`, `.jpg`, `.webp`) to `/api/assets/thumbnail`. Assert HTTP 201, valid UUID `id`, and original filename.
  - Test rejection of invalid kind `/api/assets/video` -> HTTP 404.
  - Test rejection of disallowed extension (e.g. `.exe`, `.sh`) -> HTTP 400.
  - Test rejection of missing file field -> HTTP 400.
- **Render Job Creation (`POST /api/jobs`)**:
  - Send `{ mediaId: ..., jobType: 'render', options: { backgroundAudioId: ..., thumbnailId: ..., subtitles: ... } }`.
  - Assert that `options.backgroundMusicPath` and `options.thumbnailPath` are resolved from the temporary upload store.
  - Assert that `ensure_translation_configured` is not called (render mode only requires audio mix and subtitle burn-in).
  - Assert that `clear_cache` is `False`.

#### Tier 2: Boundary & Corner Cases
- **Volume Clamping**:
  - Test inputs: `originalAudioVolume = -0.5` -> clamped to `0.0`.
  - Test inputs: `originalAudioVolume = 2.5` -> clamped to `1.5`.
  - Test inputs: `backgroundAudioVolume = -1.0` -> clamped to `0.0`.
  - Test inputs: `backgroundAudioVolume = 3.0` -> clamped to `1.5`.
  - Test `volume` parameter formatted as `+20%`, `-50%`, `+0%`.
- **Timing Constraint Enforcement in `updateStage4Timing`**:
  - When editing segment `k`'s `startSec`: must not be `< 0`, must not exceed `endSec - 0.001`, must not precede segment `k-1`'s `endSec`.
  - When editing segment `k`'s `endSec`: must not be `< startSec + 0.001`, must not exceed segment `k+1`'s `startSec`.
- **Zero & Extreme Transcripts**:
  - Test with 0 segments: timeline does not divide by zero; SRT serialization yields empty string `""`.
  - Test with 1 segment spanning 120 seconds: timeline renders track width 100%.
  - Test with segments having empty text: SRT serializer falls back cleanly without `undefined` or `null`.

#### Tier 3: Cross-Feature Interactions & Reactive Synchronization
- **Playhead Seeking & Dual Audio Sync**:
  - When playhead seeks, `syncPreviewPlayback(video)` triggers:
    - Master `<video>` seeks to `seconds`.
    - `#stage4-bgm-preview` seeks to `seconds % bgmDuration`.
    - Active segment is recalculated (`state.activeSegmentId = curSeg.id`).
    - Playhead needle `data-timeline-playhead` style updates (`left: ${percent}%`).
    - Active subtitle cue card highlights (`border-2 border-[#8D4B00] bg-amber-50/50`).
    - Subtitle overlay `[data-canvas-subtitle]` updates to active segment text.
- **Inspector Tab Switching**:
  - Clicking a subtitle block on the timeline seeks to `startSec` AND automatically switches the inspector tab to `subtitles`.
  - Clicking the Video track header switches inspector tab to `thumbnail`.
  - Clicking the Dubbed TTS or BGM track headers switches inspector tab to `audio`.

#### Tier 4: Real-World Workflow (End-to-End Execution)
- Simulate full user session:
  1. Upload source media.
  2. Transition to Stage 4.
  3. Upload background music track `ambient.mp3`.
  4. Balance audio mix: Original = 15%, Dubbed = 110%, BGM = 30%.
  5. Select Subtitle Cue #2, modify `targetText` to "Updated translation", adjust timing by +0.5s.
  6. Increase subtitle font size to 26px.
  7. Upload custom thumbnail `cover.webp`.
  8. Click "Render dubbed video" (`exportEditedVideo()`).
  9. Assert that `build_task_params` receives:
     - `source_audio_volume == 0.15`
     - `backaudio_volume == 0.30`
     - `volume == "+10%"`
     - `background_music` pointing to `ambient.mp3`
     - `thumbnail` pointing to `cover.webp`
     - `subtitles` containing "Updated translation" with new timecodes
     - `clear_cache == False`
     - `embed_bgm == True`

---

### 6. Verification Method & Commands

The test suite must be executable in any environment with:
```bash
uv run pytest tests/test_stage4_edit_video.py -v
```

Execution properties:
- **Headless**: Runs without displays, virtual frames, or web browsers.
- **Fast**: Complete file execution in under 2.0 seconds.
- **Deterministic**: No network requests, no real GPU execution, deterministic fixtures.
- **Graceful Node Fallback**: Skips Node.js tests cleanly if `node` is not in PATH, while passing all Python unit and endpoint tests.
