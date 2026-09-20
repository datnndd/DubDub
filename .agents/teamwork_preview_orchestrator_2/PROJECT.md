# Project: DubDub AI Video Dubbing Studio - Stage 4: Edit Video Redesign

## Architecture
Stage 4 ("Edit Video") transforms DubDub into an intuitive, lightweight video editing studio inspired by CapCut.
It allows users to review the final dubbed video, make adjustments to subtitles, audio tracks, and video thumbnail, and export the finished video.

The architecture comprises:
1. **Frontend Studio View Screen** (`frontend/js/screens/Stage4EditVideo.js`):
   - **Upper Deck**:
     * **Widescreen Video Preview** (cols 7-8): Video player canvas, transport controls, synchronized HUD timecode, unboxed canvas subtitle overlay.
     * **Contextual Settings Inspector** (cols 4-5): Tabbed inspector containing:
       - *Subtitles Tab*: Font size slider + number input, active subtitle cue inline editor (`targetText`, `startSec`, `endSec`), format timecodes.
       - *Audio Mix Tab*: Independent 0–150% volume sliders and mute toggles for Original Audio, Dubbed TTS, and Background Music (BGM).
       - *BGM Track Tab*: Upload, replace, remove, and preview background music files (`audio/*`).
       - *Thumbnail Tab*: Upload, replace, remove/reset video thumbnail with aspect-video preview card.
   - **Lower Deck**:
     * **Multi-Track Timeline** (height ~210px): Visual lanes for Video, Subtitles (proportional cue blocks), Dubbed TTS, and Background Music (BGM).
     * Interactive playhead needle spanning all tracks, time ruler, and click-to-seek navigation. Clicking a subtitle cue highlights it and activates its editor in the inspector.

2. **Frontend Reactive Store** (`frontend/js/state.js`):
   - Single source of truth (`window.dubDubStore`).
   - Maintains:
     * `state.editVideo`: `{ audioMix: { original: 0, dubbed: 100, background: 35 }, muted: { original: false, dubbed: false, background: false }, backgroundAudio: null, thumbnail: null, activeTab: 'subtitles', selectedCueId: null }`
     * `state.subtitleStyles`: `{ color: '#FFFFFF', outlineColor: '#000000', outlineWidth: 2, shadowSize: 2, fontSize: 22 }`
     * `state.segments`: list of dialog blocks with `startSec`, `endSec`, `targetText`.
   - Audio playback sync: synchronizes video playback with `<audio id="stage4-bgm-preview">` applying drift compensation, volume scaling, and mute states.
   - Serialization: `serializeEditedSrt()` creates valid SRT formatted string from edited segments.
   - Export action: `exportEditedVideo()` packages mix levels, asset IDs (`backgroundAudioId`, `thumbnailId`), and edited SRT into `/api/jobs` payload.

3. **Video Canvas Preview Subtitle Overlay** (`frontend/js/components/VideoPlayer.js`):
   - Supports `subtitleVariant === 'capcut'` unboxed subtitle overlay directly over video canvas.
   - Default clean styling: `#FFFFFF` font, `-webkit-text-stroke: 2px #000000`, `text-shadow: 0 2px 4px rgba(0,0,0,0.75)`, bottom-centered, dynamic font size.

4. **Backend Audio Mixing & Render Pipeline** (`webui.py`, `videotrans/task/`):
   - Asset upload endpoint: `POST /api/assets/{kind}` (`background-audio`, `thumbnail`) saves files to `UPLOAD_DIR` and returns unique asset IDs in `EDIT_ASSETS`.
   - Render job endpoint: `POST /api/jobs` with `jobType: "render"` (and ergonomic aliases if present).
   - Parameter resolution: resolves `backgroundAudioId` -> `backgroundMusicPath`, `thumbnailId` -> `thumbnailPath`.
   - Mix parameters: `originalAudioVolume` (0.0–1.5), `backgroundAudioVolume` (0.0–1.5), `volume` (dubbed voice), embedded into `TaskCfgVTT`.
   - FFmpeg audio mixing: `_back_music()` loops and mixes BGM into `target.wav`, `_mix_original_audio()` mixes `source.wav` with `source_audio_volume` into `target.wav` using `amix`.
   - Cover art embedding: `_embed_thumbnail()` embeds custom thumbnail as MP4 cover art losslessly.
   - Subtitle burning: `set_ass_font()` converts `subtitleStyle` to ASS font specifications for FFmpeg burning.

5. **Automated Verification Harness** (`tests/test_stage4_edit_video.py`):
   - Comprehensive test suite covering all tiers: API endpoints, store logic boundaries, DOM contracts, headless Node.js ES module evaluation, and E2E render workflows.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | Studio 3-Area Layout & Video Preview | 3-area layout (widescreen preview, inspector, multi-track timeline); clean unboxed canvas subtitle overlay; real-time synchronized multi-audio preview | M1 | ORIGINAL_REQUEST §R1 |
| F2 | Multi-Track Timeline Workspace | Visual tracks for Video, Subtitles, Dubbed TTS, and BGM; clickable timeline/ruler seek; interactive playhead needle; subtitle cue selection | M1 | ORIGINAL_REQUEST §R2 |
| F3 | Audio Source Separation & BGM Control | 0–150% volume sliders and mute toggles for original, dubbed TTS, and BGM; upload/replace/remove BGM; send mixed volume levels in export payload | M1 | ORIGINAL_REQUEST §R3 |
| F4 | Subtitle Typography & Inline Editing | Dynamic font size slider AND number input; inline editing of active cue text and start/end timecodes updating `state.segments` and export SRT; focus-preserved typing | M1 | ORIGINAL_REQUEST §R4 |
| F5 | Video Thumbnail Management | Upload/replace thumbnail with aspect-video preview card; remove/reset to default first frame | M1 | ORIGINAL_REQUEST §R5 |
| F6 | Backend Asset Ingestion & Render Pipeline | `/api/assets/{kind}` ingestion, asset ID resolution to disk paths, `jobType: "render"` parameter mapping, and BGM/original audio mixing | M2 | ORIGINAL_REQUEST §R3, §R5 |
| F7 | Comprehensive Automated Test Suite | Automated pytest suite in `tests/test_stage4_edit_video.py` verifying R1–R5, passing with `uv run pytest` | M3 | ORIGINAL_REQUEST §Verification |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Frontend Studio Polish & Contract Hardening | Fix subtitle typing focus loss bug (`data-segment-input="stage4-${id}"`); add number input alongside font size slider; verify multi-track timeline, canvas subtitles, audio mix, and thumbnail preview | none | PLANNED |
| M2 | Backend Asset & Export Endpoint Resilience | Ensure `/api/assets/{kind}` validates and registers assets; verify `build_task_params` with `job_type="render"`; add ergonomic aliases `/api/render` and `/api/export` if needed; verify asset ID resolution | none | PLANNED |
| M3 | E2E Automated Verification & Adversarial Gate | Construct comprehensive `tests/test_stage4_edit_video.py` covering all 6 test sections and R1–R5 acceptance criteria; execute with `uv run pytest`; run independent Reviewers, Challengers, and Forensic Auditor | M1, M2 | PLANNED |

## Interface Contracts

### 1. Backend Asset Upload Endpoint
- `POST /api/assets/{kind}`
  - Path param `kind`: `"background-audio"` or `"thumbnail"`
  - Headers: `X-Filename: <filename>`
  - Body: raw binary or multipart file
  - Allowed extensions:
    * `background-audio`: mp3, wav, aac, flac, m4a, ogg, wma, opus
    * `thumbnail`: png, jpg, jpeg, webp
  - Response (201 Created):
    ```json
    { "id": "<uuid-hex>", "name": "<filename>" }
    ```

### 2. Backend Render Job Request Payload
- `POST /api/jobs`
  ```json
  {
    "mediaId": "<media-id>",
    "jobType": "render",
    "options": {
      "subtitles": "<full-srt-text>",
      "subtitleStyle": {
        "fontSize": 22,
        "color": "#FFFFFF",
        "outlineColor": "#000000",
        "outlineWidth": 2,
        "shadowSize": 2
      },
      "originalAudioVolume": 0.0,
      "volume": "+0%",
      "backgroundAudioVolume": 0.35,
      "backgroundAudioId": "<asset-id-or-null>",
      "thumbnailId": "<asset-id-or-null>"
    }
  }
  ```

### 3. Frontend Store State (`window.dubDubStore.state`)
- `state.editVideo`:
  - `audioMix`: `{ original: number, dubbed: number, background: number }` (0–150)
  - `muted`: `{ original: boolean, dubbed: boolean, background: boolean }`
  - `backgroundAudio`: `{ id: string, name: string, url: string } | null`
  - `thumbnail`: `{ id: string, name: string, url: string } | null`
  - `activeTab`: `'subtitles' | 'audio' | 'bgm' | 'thumbnail'`
  - `selectedCueId`: string | number | null
- `state.subtitleStyles`:
  - `fontSize`: number (8–64)
  - `color`: string (`#FFFFFF`)
  - `outlineColor`: string (`#000000`)
  - `outlineWidth`: number
  - `shadowSize`: number
- Key Store Methods:
  - `updateAudioMix(channel, volume)`
  - `toggleAudioMute(channel)`
  - `selectBackgroundAudio(file)`
  - `removeBackgroundAudio()`
  - `selectThumbnail(file)`
  - `removeThumbnail()`
  - `updateSubtitleStyle(styles)`
  - `updateStage4Subtitle(segmentId, text)`
  - `updateStage4Timing(segmentId, startSec, endSec)`
  - `serializeEditedSrt()`
  - `exportEditedVideo()`

### 4. DOM Contract Attributes
- Studio layout root: `[data-stage4-studio]`
- Video preview canvas subtitle: `[data-canvas-subtitle]`
- Video preview canvas speaker badge: `[data-canvas-speaker-badge]`
- Timeline container: `[data-timeline-container]`
- Timeline playhead needle: `[data-timeline-playhead]`
- Timeline tracks: `[data-timeline-track="video"]`, `[data-timeline-track="subtitles"]`, `[data-timeline-track="dubbing"]`, `[data-timeline-track="bgm"]`
- Timeline cue element: `[data-timeline-cue="{segmentId}"]`
- Inspector tabs: `[data-inspector-tab="subtitles"]`, `[data-inspector-tab="audio"]`, `[data-inspector-tab="bgm"]`, `[data-inspector-tab="thumbnail"]`
- Font size slider: `[data-action="update-font-size"]`
- Font size number input: `[data-action="update-font-size-input"]`
- Active subtitle textarea: `[data-stage4-subtitle="{segmentId}"][data-segment-input="stage4-{segmentId}"]`
- Audio mix sliders: `[data-mix-slider="original"]`, `[data-mix-slider="dubbed"]`, `[data-mix-slider="background"]`
- Audio mute toggles: `[data-action="toggle-mute-original"]`, `[data-action="toggle-mute-dubbed"]`, `[data-action="toggle-mute-background"]`
- BGM input: `#stage4-background-input`
- BGM preview audio element: `#stage4-bgm-preview`
- Thumbnail input: `#stage4-thumbnail-input`
- Thumbnail preview card: `[data-thumbnail-preview]`
- Export / Render button: `[data-action="export-edited-video"]`

## Code Layout
- `webui.py`: Backend REST API, asset upload handler, render job creation.
- `videotrans/task/`: Audio mixing (`_stage_audio.py`), assemble (`_stage_assemble.py`), thumbnail embedding (`orchestrator.py`).
- `videotrans/util/_srt_ass.py`: ASS subtitle styling conversion.
- `frontend/js/screens/Stage4EditVideo.js`: Stage 4 3-area studio UI screen.
- `frontend/js/components/VideoPlayer.js`: Video player with CapCut canvas subtitle overlay.
- `frontend/js/state.js`: Reactive store, audio sync, state mutations, SRT serialization.
- `tests/test_stage4_edit_video.py`: Stage 4 automated verification test suite.
