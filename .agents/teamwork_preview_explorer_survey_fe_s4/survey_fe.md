# Frontend Survey & Technical Specification: Stage 4 CapCut-Inspired Video Editing Studio

**Author**: `explorer_survey_fe`  
**Date**: 2026-09-20  
**Target Component**: Stage 4 (`Stage4EditVideo.js`, `state.js`, `VideoPlayer.js`, `StatusFooter.js`)  
**Repository**: `pyvideotrans` (DubDub AI Video Dubbing Studio)

---

## 1. Executive Summary

Stage 4 ("Edit Video") transforms DubDub from a sequential translation pipeline into an intuitive, lightweight video editing workspace inspired by CapCut Desktop. The design provides creators with high-fidelity review and adjustment capabilities—subtitle typography tuning, 3-way audio source balancing (original, dubbed voiceover, background music), video thumbnail assignment, and proportional multi-track timeline navigation—prior to final video rendering and export.

The frontend is implemented with zero heavy UI framework overhead, leveraging standard ES modules, Tailwind CSS utility classes, Material Symbols Outlined icons, and an observable singleton state store (`WorkflowStore` / `window.dubDubStore`).

---

## 2. Current Frontend Codebase Architecture

### 2.1 File Map & Responsibilities

| File Path | Role & Stage 4 Relevance |
|---|---|
| `frontend/js/screens/Stage4EditVideo.js` | Main Stage 4 screen layout: 3-area studio (Video Preview, Contextual Inspector, Multi-Track Timeline). |
| `frontend/js/state.js` | Central synchronized state store (`WorkflowStore`). Manages `state.editVideo`, `state.subtitleStyles`, audio mixing, BGM synchronization, timecode scrubbing, SRT serialization, and render job submission. |
| `frontend/js/components/VideoPlayer.js` | Reusable player component. Houses the `subtitleVariant === 'capcut'` unboxed subtitle overlay, timecode HUD badge, and video event listeners. |
| `frontend/js/components/StatusFooter.js` | Persistent bottom dock. Binds primary action button to `exportEditedVideo()` when `currentStep === 4`. |
| `frontend/js/app.js` | Application coordinator. Mounts header, workflow stepper, active stage screen, and status footer; handles input focus restoration. |
| `frontend/index.html` & `frontend/css/styles.css` | Tailwind config, Google Fonts (Plus Jakarta Sans, JetBrains Mono, Inter, Montserrat), custom scrollbars, and range slider thumb styling. |
| `frontend/assets/screen_1_edit_video.html` | High-fidelity reference mockup for CapCut Desktop Pro timeline deck layout and color palette. |

---

## 3. UI Layout & Component Analysis

### 3.1 3-Area Studio Layout
The Stage 4 interface divides the viewport into two decks within an overall flexbox column:
1. **Upper Deck (Flex-1 / Grid 12 cols)**:
   - **Top-Left: Widescreen Video Preview (7-8 cols)**:
     - 16:9 responsive video container rendering `<video data-source-preview>`.
     - Floating HUD telemetry badges: synchronized playhead timecode (`MM:SS.mmm / Total`) and speaker badge.
     - Transport controls: play/pause, seek start.
     - Direct canvas subtitle overlay (`[data-canvas-subtitle]`) positioned near bottom center.
   - **Top-Right: Contextual Settings Inspector (4-5 cols)**:
     - 3-tab navigation header (`Audio Mix`, `Subtitles`, `Thumbnail`).
     - Scrollable configuration body with dedicated settings for each domain.
2. **Lower Deck (Fixed Height 210px)**:
   - **Multi-Track Timeline**:
     - Toolbar: Play/pause button, timecode readout (`currentTime / totalDuration`), Seek Start button, track color legend badges.
     - Track Headers Column (144px width): Labels and icons for Timeline Ruler, Video (16:9), Subtitles (count), Dubbed TTS (volume %), and BGM (volume %).
     - Interactive Track Lanes & Ruler: Proportional timeline spanning all cues, clickable seek anywhere on tracks/ruler, and vertical playhead needle spanning all 4 tracks.

---

### 3.2 Visual Specifications & Contracts

#### A. Canvas Subtitle Overlay (Clean CapCut Style)
- **Container**: Positioned at bottom center (`absolute inset-x-3 bottom-4 z-20 flex justify-center text-center pointer-events-none`).
- **Typography & Styling**:
  - Unwrapped text: Direct paragraph element `<p data-canvas-subtitle>` without card borders or background pill boxes.
  - Text Color: `#FFFFFF` (pure white).
  - Outline: 2px solid black (`-webkit-text-stroke: 2px #000000; paint-order: stroke fill;`).
  - Drop Shadow: Subtle drop shadow (`text-shadow: 0 2px 4px rgba(0, 0, 0, 0.75);`).
  - Font Size: User adjustable from 14px to 48px (default: 22px / 24px).
  - Font Family: Selectable (Arial, Inter, Montserrat, Plus Jakarta Sans, Roboto).
  - Text Alignment: Center (`text-align: center;`).

#### B. Contextual Inspector Tabs
1. **Tab 1: Audio Mix (`activeTab === 'audio'`)**:
   - 3 separate volume sliders with icons, labels, mute toggles, and percentage readouts:
     - Original Video Audio (`key = 'original'`, default: `0%`)
     - Dubbed TTS Audio (`key = 'dubbed'`, default: `100%`)
     - Background Music (`key = 'background'`, default: `35%`)
   - Range: `0%` to `150%`.
   - Mute button toggles between muted (`0%`) and previous volume level (`prevMix`).
   - BGM Asset Manager:
     - Hidden `<input id="stage4-background-input" type="file" accept="audio/*">`.
     - If BGM loaded: shows track chip with name, "Synchronized with master playhead" badge, "Replace" button, and "Remove BGM" link.
     - If no BGM: dashed upload dropzone ("Add Background Music").
2. **Tab 2: Subtitles (`activeTab === 'subtitles'`)**:
   - Subtitle Appearance:
     - Font size dual controls (range slider + numeric input / readout).
     - Font family dropdown.
     - Text color picker.
     - Outline width slider (0px to 5px).
     - Shadow size slider (0px to 6px).
   - Selected Cue Editor:
     - Header: Active Cue ID badge (`Cue #01`), Prev Cue / Next Cue navigation buttons.
     - Timestamp Editors: Numeric inputs for `startSec` and `endSec` with step 0.001s.
     - Subtitle Text Editor: Inline `<textarea>` for editing `targetText`.
3. **Tab 3: Thumbnail (`activeTab === 'thumbnail'`)**:
   - Hidden `<input id="stage4-thumbnail-input" type="file" accept="image/png,image/jpeg,image/webp">`.
   - If thumbnail loaded: 16:9 aspect-video preview card with hover action overlay ("Change Image", "Remove"), file name, and reset link.
   - If no thumbnail: Dashed dropzone with "No Custom Thumbnail" notice ("First frame of the video will be used by default") and "Upload Thumbnail" button.

#### C. Multi-Track Timeline
- **Track 1: Video Track Lane**:
  - Clip block showing source video file name and resolution badge (`16:9`).
- **Track 2: Subtitles Track Lane**:
  - Proportional cue chips: `left = (seg.startSec / duration) * 100%`, `width = ((seg.endSec - seg.startSec) / duration) * 100%`.
  - Selected cue highlighted with `bg-amber-400 font-bold border-[#8D4B00] shadow-xs`.
  - Tooltip: `startSec → endSec: targetText`.
  - Click behavior: Seeks to `startSec`, sets `activeSegmentId`, opens Subtitles inspector tab.
- **Track 3: Dubbed TTS Audio Track Lane**:
  - Proportional speech blocks colored indigo (`bg-indigo-100 border-indigo-300`).
  - Badge showing speaker name / assigned TTS voice (`seg.voiceOverride || seg.speakerName`).
  - Click behavior: Seeks to `startSec`, opens Audio Mix tab in inspector.
- **Track 4: Background Music Track Lane**:
  - If BGM loaded: Full-length emerald block (`bg-emerald-100 border-emerald-300`) displaying track name and volume %.
  - If no BGM: Dashed "+ Add BGM track" button that opens file picker.
- **Scrubber Needle (`[data-timeline-playhead]`)**:
  - Spans the entire height across all 4 tracks.
  - Amber vertical needle (`w-0.5 bg-amber-500`) topped with a downward marker pin.
  - Position dynamically updated in real time via `syncPreviewPlayback` (`left: (currentTime / duration) * 100%`).

---

## 4. State Management & Synchronization Architecture

### 4.1 State Tree (`state.js`)
```javascript
state = {
  currentStep: 4,
  activeSegmentId: 1,
  project: {
    durationSec: 86.4,
    previewUrl: "blob:...",
    resolution: "1920x1080",
    ...
  },
  playback: {
    currentTime: 0,
    formattedTime: "00:00.000",
    isPlaying: false,
    playbackSpeed: 1.0,
    audioChannel: "dub"
  },
  subtitleStyles: {
    preset: "clean",
    fontFamily: "Arial",
    fontSize: 22,
    color: "#FFFFFF",
    outlineColor: "#000000",
    outlineWidth: 2,
    shadowColor: "rgba(0,0,0,.75)",
    shadowSize: 2
  },
  editVideo: {
    audioMix: {
      original: 0,     // 0-150%
      dubbed: 100,     // 0-150%
      background: 35   // 0-150%
    },
    prevMix: {},       // Stores unmuted volume before mute toggle
    backgroundAudio: null, // { id, name, previewUrl, uploading }
    thumbnail: null,       // { id, name, previewUrl, uploading }
    exporting: false,
    error: null,
    activeTab: "audio"     // 'audio' | 'subtitles' | 'thumbnail'
  },
  segments: [
    {
      id: 1,
      speakerId: "spk_1",
      speakerName: "Alex Carter",
      startSec: 81.0,
      endSec: 86.4,
      sourceText: "...",
      targetText: "...",
      voiceOverride: null
    },
    ...
  ]
};
```

### 4.2 Playback & Audio Synchronization Pipeline
In `state.js`, the method `syncPreviewPlayback(media)` coordinates all active media elements on every `timeupdate`, `play`, `pause`, and `seek`:
1. **Video Playhead**:
   - `media.currentTime` reads current playhead position.
   - Updates `state.playback.currentTime` and formatted timecode (`[data-playhead-timecode]`).
   - Updates needle position `[data-timeline-playhead].style.left = ${percent}%`.
2. **Dynamic Subtitle Synchronization**:
   - Finds active segment where `seg.startSec <= seconds <= seg.endSec`.
   - Updates `[data-canvas-subtitle].textContent` immediately without full DOM teardown.
   - Highlights active cue block on timeline (`[data-segment-card]`).
3. **Audio Balancing & Background Music**:
   - Video element volume: `media.volume = Math.max(0, Math.min(1, origVol / 100))`, `media.muted = (origVol === 0)`.
   - Background music element (`<audio id="stage4-bgm-preview">`):
     - Volume: `bgm.volume = Math.max(0, Math.min(1, bgmVol / 100))`, `bgm.muted = (bgmVol === 0)`.
     - Play/Pause state mirrors video: pauses when video pauses, resumes when video plays.
     - Clock drift compensation: If `Math.abs(bgm.currentTime - expectedTime) > 0.35`, resyncs `bgm.currentTime = expectedTime`.

### 4.3 Export Pipeline Integration
When the user clicks "Render dubbed video" in `StatusFooter`:
1. `exportEditedVideo()` serializes segments into standard SRT via `serializeEditedSrt()`.
2. Assembles request payload:
   ```json
   {
     "mediaId": "...",
     "jobType": "render",
     "options": {
       "subtitles": "1\n00:00:00,000 --> 00:00:05,000\n...",
       "volume": "+0%",
       "originalAudioVolume": 0.0,
       "backgroundAudioVolume": 0.35,
       "backgroundAudioId": "uuid-bgm",
       "thumbnailId": "uuid-thumb",
       "subtitleStyle": {
         "fontSize": 22,
         "color": "#FFFFFF",
         "outlineWidth": 2,
         "shadowSize": 2
       }
     }
   }
   ```
3. Posts to `POST /api/jobs`.
4. Backend `webui.py` sets `clear_cache = False` (preserving extracted audio & synthesized dubs), mounts the background music track at `backgroundAudioVolume`, scales original dialogue at `originalAudioVolume`, burns subtitles with `subtitleStyle`, embeds the thumbnail, and executes the render task.

---

## 5. DOM Contract & Test Assertion Matrix

The frontend implementation must strictly maintain the following DOM contract attributes and hooks for UI operation and automated verification (`tests/test_stage4_edit_video.py`):

| Contract Selector / Attribute | Element | Purpose / Verified By Test |
|---|---|---|
| `[data-timeline-playhead]` | `<div>` | Scrubber playhead needle spanning all timeline tracks. |
| `[data-playhead-timecode]` | `<span>` | Synchronized playhead timecode readout (`MM:SS.mmm`). |
| `[data-segment-card="${id}"]` | `<div>` | Proportional subtitle cue block on timeline. Click seeks and activates cue. |
| `[data-mix-slider="${key}"]` | `<input type="range">` | Independent volume sliders for `original`, `dubbed`, `background`. |
| `[data-canvas-subtitle]` | `<p>` | Overlay text rendered directly over video canvas. |
| `#stage4-bgm-preview` | `<audio>` | Hidden audio element for synchronized client BGM playback. |
| `#stage4-background-input` | `<input type="file">` | File input for uploading/replacing background music. |
| `#stage4-thumbnail-input` | `<input type="file">` | File input for uploading/replacing video cover thumbnail. |
| `[data-stage4-subtitle="${id}"]` | `<textarea>` | Inline editor for active subtitle cue text in inspector. |
| `data-action="next-step"` | `<button>` in footer | Triggers `exportEditedVideo()` when on Stage 4. |

---

## 6. Critical Findings & Technical Recommendations

During deep code exploration of `Stage4EditVideo.js`, `state.js`, and `app.js`, we identified several subtle bugs and opportunities for polish:

### ⚠️ Finding 1: Subtitle Textarea Typing Loss of Focus Bug
- **Observation**: In `state.js`, `updateSegmentTargetText` prevents full app re-renders during active typing by checking:
  ```javascript
  const isActivelyTyping = activeEl && activeEl.getAttribute('data-segment-input') === `stage3-${segmentId}`;
  ```
  However, the Stage 4 subtitle textarea in `Stage4EditVideo.js` currently defines:
  ```html
  <textarea data-stage4-subtitle="${esc(active?.id)}" ...>
  ```
  It lacks the `data-segment-input="stage4-${active.id}"` attribute!
- **Consequence**: When the user types a character in the Stage 4 subtitle textarea, `isActivelyTyping` evaluates to `false`. This triggers `this.notify()`, causing `renderApp()` in `app.js` to rebuild `root.innerHTML`. Because `app.js` looks for `[data-segment-input]`, it fails to restore focus to `[data-stage4-subtitle]`. As a result, the user loses cursor focus after typing a single keystroke.
- **Recommendation**:
  1. Add `data-segment-input="stage4-${esc(active?.id)}"` to the textarea in `Stage4EditVideo.js`.
  2. Update `updateSegmentTargetText` in `state.js` to check:
     ```javascript
     const isActivelyTyping = activeEl && (
       activeEl.getAttribute('data-segment-input') === `stage3-${segmentId}` ||
       activeEl.getAttribute('data-segment-input') === `stage4-${segmentId}`
     );
     ```
  3. Ensure `canvasSub.textContent` updates synchronously in the DOM on input, and only trigger full re-render on blur.

---

### ⚠️ Finding 2: Font Size Control Missing Number Input
- **Observation**: Requirement R4 explicitly states:
  > *"Allow adjusting subtitle font size dynamically via a slider and number input, updating the preview canvas immediately."*
  Currently in `Stage4EditVideo.js`, there is only a range slider and a static `<output>` label.
- **Recommendation**:
  Provide an interactive `<input type="number" min="12" max="64" class="..." value="${style.fontSize || 22}">` alongside the slider. Synchronize both inputs so typing a number immediately updates the slider, and dragging the slider immediately updates the number input and canvas subtitle font size.

---

### ⚠️ Finding 3: Dragging Sliders Triggers Video Interruption
- **Observation**: In `Stage4EditVideo.js`, dragging the subtitle font size slider on `oninput` calls `window.dubDubStore.updateSubtitleStyle('fontSize', Number(this.value))`. Because `updateSubtitleStyle` unconditionally calls `this.notify()`, the entire application DOM is torn down on every mousemove event. If a video is playing, this unmounts the `<video>` element, causing playback stutter or video reloads.
- **Recommendation**:
  Adopt the same pattern used by `audioSlider`:
  - On `oninput`: Directly update the CSS style of `[data-canvas-subtitle]` (`el.style.fontSize = value + 'px'`) and update store state with `notify = false`.
  - On `onchange`: Call `updateSubtitleStyle(field, value, notify = true)` to persist the value into state.

---

### ⚠️ Finding 4: Multi-Track Timeline Scrub Dragging
- **Observation**: Currently, the timeline and time ruler only listen to `onclick`. A user clicking a position seeks properly, but clicking and dragging the playhead needle does not update continuously.
- **Recommendation**:
  Add `onpointerdown` and `onpointermove` handlers to the timeline container to enable smooth continuous scrubbing while dragging the playhead needle across tracks.

---

## 7. Conclusion
The current Stage 4 foundation is architecturally well-aligned with the CapCut studio vision: it features clean unboxed canvas subtitles, independent audio volume mixing, BGM upload and synchronization, thumbnail management, and a proportional multi-track timeline. Applying the recommendations above—specifically fixing the textarea focus bug, adding the synchronized number input for font size, and optimizing real-time dragging—will elevate the studio to production-grade polish.
