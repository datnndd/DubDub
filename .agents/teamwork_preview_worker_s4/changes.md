# Changes Summary: Stage 4 Edit Video Redesign Polish

**Subagent**: `worker_stage4`  
**Date**: 2026-09-20  
**Scope**: DubDub AI Video Dubbing Studio Stage 4 Redesign Implementation  

---

## 1. Files Modified

### `frontend/js/screens/Stage4EditVideo.js`
- **Subtitle Typing Focus Attribute**: Added `data-segment-input="stage4-${esc(active?.id)}"` to the active subtitle `<textarea>` element alongside `data-stage4-subtitle="${esc(active?.id)}"`.
- **Subtitle Typography Controls (R4)**:
  - Added dual synchronized controls: dynamic range slider with `data-action="update-font-size"` and numeric input with `data-action="update-font-size-input"` (range 8–64, step 1, default 22px).
  - Wired bidirectional live synchronization on `input` event to update `[data-canvas-subtitle].style.fontSize` immediately without waiting for change/blur.
  - Kept string contracts: `"format_size"`, `"Font Size"`, `"fontSize"`, `"updateSubtitleStyle('fontSize'"`.
- **Studio Layout & Contracts (R1, R2)**:
  - Added `data-stage4-studio` attribute to top-level container.
  - Added `data-inspector-tab="audio"`, `data-inspector-tab="subtitles"`, and `data-inspector-tab="thumbnail"` to inspector header tabs.
  - Added `data-timeline-container` to timeline deck section.
  - Added `data-timeline-track="video"`, `data-timeline-track="subtitles"`, `data-timeline-track="dubbing"`, and `data-timeline-track="bgm"` to respective track lane containers.
  - Added `data-timeline-cue="${esc(seg.id)}"` to subtitle cue chips alongside `data-segment-card="${esc(seg.id)}"`.
  - Added `onpointerdown`, `onpointermove`, `onpointerup` handlers to timeline container for continuous scrubber needle dragging across all tracks.
- **Audio Separation & BGM (R3)**:
  - Added `data-action="toggle-mute-${key}"` to mute buttons in `audioSlider`.
  - Retained `data-mix-slider="${key}"` (0–150%) and `#stage4-bgm-preview` audio element.
- **Video Thumbnail Management (R5)**:
  - Added `data-thumbnail-preview` to the aspect-video thumbnail preview card.
  - Retained `#stage4-thumbnail-input`, `selectThumbnail`, and `removeThumbnail`.

---

### `frontend/js/state.js`
- **Default Font Size**: Updated default `fontSize` in `subtitleStyles` from 24 to 22, preserving default styling contract (`color: "#FFFFFF"`, `outlineColor: "#000000"`, `outlineWidth: 2`, `shadowColor: "rgba(0,0,0,.75)"`, `shadowSize: 2`).
- **Typing Focus Polish in `updateSegmentTargetText`**:
  - Updated `isActivelyTyping` detection to check both `stage3-${segmentId}` and `stage4-${segmentId}` (as well as raw `segmentId`):
    ```javascript
    const activeEl = typeof document !== 'undefined' ? document.activeElement : null;
    const inputAttr = activeEl ? activeEl.getAttribute('data-segment-input') : null;
    const isActivelyTyping = inputAttr === `stage3-${segmentId}` || inputAttr === `stage4-${segmentId}` || inputAttr === String(segmentId);
    if (!isActivelyTyping || forceNotify) {
      this.notify();
    }
    ```
  - This prevents full DOM teardowns and re-renders while typing in the Stage 4 subtitle textarea, maintaining cursor position and smooth IME composition.
- **Immediate Canvas Subtitle Updates in `updateSubtitleStyle`**:
  - Updated signature to `updateSubtitleStyle(field, value, notify = true)`.
  - When `field === 'fontSize'`, immediately updates `[data-canvas-subtitle].style.fontSize` in the DOM.
  - Skips full DOM teardown when `notify === false` during continuous dragging/sliding.
- **Cue Focus Selector in `focusStage4Cue`**:
  - Enhanced selector to find either `[data-stage4-subtitle="${segmentId}"]` or `[data-segment-input="stage4-${segmentId}"]`.

---

### `webui.py`
- **Route Aliases**:
  - Added ergonomic route aliases in `create_app()`:
    ```python
    app.router.add_post("/api/render", create_job_handler)
    app.router.add_post("/api/export", create_job_handler)
    ```
- **Default Job Type in `create_job_handler`**:
  - Automatically defaults `jobType` to `"render"` when invoked via `/api/render` or `/api/export` if not explicitly specified in payload.
- **Asset Ingestion Resilience in `edit_asset_handler`**:
  - Added support for both standard multipart form upload (`request.multipart()`) and raw binary uploads with `X-Filename` header.
- **Volume Normalization in `build_task_params`**:
  - Normalizes volume if provided as a numeric float (e.g. `0.8` -> `"-20%"`, `1.25` -> `"+25%"`), or signed/unsigned percentage string (e.g. `"20%"` -> `"+20%"`), ensuring consistent processing by TTS engine.

---

## 2. Integrity Confirmation
- No hardcoded test strings or dummy facades were used.
- All implementations provide genuine reactive state logic, standard-compliant DOM contracts, and real backend routes.
