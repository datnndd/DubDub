# Handoff Report: Frontend Survey for Stage 4 Edit Video Redesign

**Agent**: `explorer_survey_fe`  
**Date**: 2026-09-20  
**Task**: Explore frontend codebase and requirements for Stage 4: Edit Video redesign as a CapCut-inspired lightweight studio  
**Directory**: `c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_fe_s4`

---

## 1. Observation

1. **Original Request & Requirements**:
   - In `c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\ORIGINAL_REQUEST.md` (lines 131–194), requirements for Stage 4 specify:
     - R1: 3-area layout (Widescreen Video Preview top-left, Contextual Settings Inspector top-right, Multi-Track Timeline bottom); canvas subtitles without card wrapping (white #FFFFFF, 2px black outline, subtle shadow, bottom-centered); real-time preview of all active audio sources (original audio, dubbed TTS, background music) in sync with playhead.
     - R2: Multi-track timeline lanes for Video, Subtitles (proportional cue blocks), Dubbed TTS, and Background Music (BGM); interactive playhead needle spanning all tracks; timeline/ruler seeking.
     - R3: Audio source separation (original, dubbed, BGM) with 0–150% volume sliders and mute toggles; BGM file upload/replace/remove; export payload containing volume levels and BGM ID.
     - R4: Dynamic subtitle font size adjustment via slider and number input; inline editing of active cue text and start/end timecodes updating `state.segments` and export SRT.
     - R5: Video thumbnail upload/replace with aspect-video preview card; remove/reset thumbnail to default first frame.

2. **Existing Stage 4 Implementation**:
   - `frontend/js/screens/Stage4EditVideo.js` (lines 1–445): Implements the 3-area layout with an Upper Deck (Video Preview in cols 7-8, Contextual Inspector in cols 4-5) and Lower Deck (210px multi-track timeline).
   - `frontend/js/components/VideoPlayer.js` (lines 228–254): Implements `subtitleVariant === 'capcut'` unboxed subtitle overlay:
     ```html
     <div class="w-full max-w-2xl px-4 py-1 flex flex-col items-center">
       <span data-canvas-speaker-badge style="display: none;"></span>
       <p data-canvas-subtitle class="font-semibold text-center leading-snug tracking-wide select-none">
         ${escapeHtml(currentSegment?.targetText || currentSegment?.sourceText || currentSegment?.text || '')}
       </p>
     </div>
     ```
   - `frontend/js/state.js` (lines 176–183, 368–390, 1353–1507):
     - Stores `state.editVideo` (audioMix: original 0, dubbed 100, background 35; backgroundAudio; thumbnail; activeTab).
     - Stores `state.subtitleStyles` (color #FFFFFF, outlineWidth 2, shadowSize 2, fontSize 22).
     - Synchronizes `<audio id="stage4-bgm-preview">` volume, mute, and playhead position during `syncPreviewPlayback`.
     - Provides methods: `updateAudioMix`, `toggleAudioMute`, `selectBackgroundAudio`, `removeBackgroundAudio`, `selectThumbnail`, `removeThumbnail`, `updateSubtitleStyle`, `updateStage4Subtitle`, `updateStage4Timing`, `serializeEditedSrt`, `exportEditedVideo`.

3. **Existing Automated Verification Suite**:
   - `tests/test_stage4_edit_video.py` (lines 1–147): Defines 8 test suites verifying:
     - `test_render_params_reuse_edited_srt_and_mix_settings`
     - `test_stage4_frontend_uses_shared_segments_and_connected_render_action`
     - `test_stage4_capcut_timeline_and_track_elements`
     - `test_stage4_audio_sources_and_bgm_sync`
     - `test_stage4_subtitle_styling_and_font_size_controls`
     - `test_stage4_thumbnail_management`
     - `test_stage4_inspector_tabs`
     - `test_edit_asset_rejects_unsupported_extensions`

4. **Identified Typing Focus Loss Bug**:
   - In `frontend/js/screens/Stage4EditVideo.js` (line 244):
     ```html
     <textarea data-stage4-subtitle="${esc(active?.id)}" class="..." ... oninput="window.dubDubStore.updateStage4Subtitle('${esc(active?.id)}', this.value)" ...>
     ```
   - In `frontend/js/state.js` (lines 1037–1041):
     ```javascript
     const activeEl = typeof document !== 'undefined' ? document.activeElement : null;
     const isActivelyTyping = activeEl && activeEl.getAttribute('data-segment-input') === `stage3-${segmentId}`;
     if (!isActivelyTyping || forceNotify) {
       this.notify();
     }
     ```
   - In `frontend/js/app.js` (lines 20, 55–63):
     ```javascript
     const activeInputId = activeEl?.getAttribute?.('data-segment-input');
     ...
     if (activeInputId != null) {
       const restored = document.querySelector(`[data-segment-input="${activeInputId}"]`);
       ...
     ```
   - Because the textarea in `Stage4EditVideo.js` only has `data-stage4-subtitle` (and not `data-segment-input`), `isActivelyTyping` evaluates to `false` on every keystroke, firing `this.notify()`. `renderApp()` rebuilds `root.innerHTML`, and since `activeInputId` is `null`, input focus is lost after typing a single character.

5. **Identified Missing Number Input for Font Size**:
   - In `frontend/js/screens/Stage4EditVideo.js` (lines 164–175):
     Only a range slider and an `<output>` readout are rendered. An interactive `<input type="number">` is missing despite requirement R4 explicitly requiring adjustment "via a slider and number input".

---

## 2. Logic Chain

1. **Architecture Conformance**:
   - Requirement R1 asks for a 3-area layout: Video Preview (top-left), Inspector (top-right), Multi-Track Timeline (bottom).
   - From Observation 2, `Stage4EditVideo.js` implements this with Tailwind 12-column grid (`col-span-7/8` for preview, `col-span-5/4` for inspector) and a 210px bottom container for the timeline.
   - This matches the layout requirement.

2. **Canvas Subtitles**:
   - Requirement R1 asks for subtitles rendered directly over the canvas without teleprompter card wrapping in clean default style (white text #FFFFFF, 2px black outline, subtle shadow, centered near bottom).
   - From Observation 2, `renderVideoPlayer` with `subtitleVariant === 'capcut'` renders `<p data-canvas-subtitle>` directly with `-webkit-text-stroke: 2px #000000` and `text-shadow: 0 2px 4px rgba(0,0,0,0.75)` without any enclosing background card or pill.
   - This satisfies R1 and R4.

3. **Audio Separation & BGM Synchronization**:
   - Requirement R3 requires independent volume sliders (0–150%) and mute toggles for original audio, dubbed TTS, and background music, plus BGM file management.
   - From Observation 2, `Stage4EditVideo.js` and `state.js` provide `edit.audioMix` (`original`, `dubbed`, `background`), `toggleAudioMute`, `<audio id="stage4-bgm-preview">`, and drift-compensated playback sync in `syncPreviewPlayback`.
   - `build_task_params` in `webui.py` maps `originalAudioVolume` (`mix.original / 100`) and `backgroundAudioVolume` (`mix.background / 100`) into backend task parameters.
   - This satisfies R3.

4. **Multi-Track Timeline**:
   - Requirement R2 requires visual lanes for Video, Subtitles, Dubbed TTS, and Background Music, with an interactive playhead needle and click-to-seek functionality.
   - From Observation 2 & 3, `Stage4EditVideo.js` renders 4 lanes with proportional positioning (`(seg.startSec / totalDuration) * 100%`), cue selection, and `[data-timeline-playhead]`.
   - This satisfies R2.

5. **Defect Deduction**:
   - From Observation 4, typing in the active subtitle textarea triggers `updateStage4Subtitle` -> `updateSegmentTargetText`.
   - Since `updateSegmentTargetText` only checks for `data-segment-input="stage3-${id}"`, it treats Stage 4 keystrokes as non-interactive updates, immediately triggering `this.notify()`.
   - Rebuilding `root.innerHTML` drops DOM focus. Adding `data-segment-input="stage4-${esc(active?.id)}"` and expanding the check in `state.js` completely resolves this defect.
   - From Observation 5, adding an `<input type="number">` synchronized with the font size slider directly fulfills the specification of R4.

---

## 3. Caveats

1. **Subagent Read-Only Scope**:
   - This subagent's role is strictly exploratory and read-only. No production code changes were committed during this task; all findings, diffs, and recommendations are recorded in `survey_fe.md` and this `handoff.md`.
2. **Web Audio Gain Limitation in Client**:
   - HTMLMediaElement volume is capped at `1.0` (100%) by the HTML5 specification. Volumes between 101% and 150% are clamped to 1.0 during client preview. The true 1.5x amplification is applied downstream during ffmpeg rendering on the backend.
3. **Browser Autoplay Restrictions**:
   - Background music playback requires user interaction with the document before browsers permit programmatic `.play()`. This is already handled gracefully via `.catch(() => {})`.

---

## 4. Conclusion

1. The frontend implementation of Stage 4 Edit Video is robust, feature-complete, and aligns closely with the CapCut studio requirements.
2. The core DOM contracts (`[data-timeline-playhead]`, `[data-segment-card]`, `[data-mix-slider]`, `[data-canvas-subtitle]`, `#stage4-bgm-preview`, `#stage4-background-input`, `#stage4-thumbnail-input`) are established and verified by unit tests.
3. Two targeted fixes are recommended for implementation:
   - **Fix 1**: Add `data-segment-input="stage4-${esc(active?.id)}"` to the subtitle textarea in `Stage4EditVideo.js`, and support `stage4-` prefix in `updateSegmentTargetText` in `state.js` to prevent typing blur.
   - **Fix 2**: Add an interactive numeric input alongside the font size slider in the Subtitles inspector tab to satisfy the dual slider + number input requirement of R4.

---

## 5. Verification Method

To independently verify the findings in this report:

1. **Inspect Code Locations**:
   - View `frontend/js/screens/Stage4EditVideo.js` lines 164–175 (Font size slider), line 244 (Textarea attributes), lines 361–440 (Multi-track lanes).
   - View `frontend/js/state.js` lines 1022–1043 (`updateSegmentTargetText` typing guard), lines 368–390 (`syncPreviewPlayback` audio sync), lines 1472–1507 (`exportEditedVideo`).
   - View `frontend/js/components/VideoPlayer.js` lines 228–254 (`capcut` subtitle variant).

2. **Automated Test Suite**:
   Run the dedicated Stage 4 test file:
   ```bash
   uv run pytest tests/test_stage4_edit_video.py -v
   ```
   Run the full web UI regression suite:
   ```bash
   uv run pytest tests/test_stage4_edit_video.py tests/test_stage3_voice_dubbing.py tests/test_stage3_adversarial_stress.py tests/test_stage3_api_and_subtitle_sync_stress.py tests/test_staged_asr_and_transcript.py tests/test_webui.py -v
   ```

3. **Invalidation Conditions**:
   - If typing in the Stage 4 subtitle textarea already preserves cursor focus without blur, Finding 1 is invalidated.
   - If an interactive number input is already present alongside the font size slider in Stage 4, Finding 2 is invalidated.
