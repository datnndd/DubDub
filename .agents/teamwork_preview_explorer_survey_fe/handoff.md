# Handoff Report: Stage 3 Voice & Dubbing Frontend Exploration

**Agent Directory:** `c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_fe`  
**Handoff Type:** Hard (Exploration task complete)  
**Target Audience:** Orchestrator & Implementation Agents  

---

## 1. Observation

1. **Frontend Serving & Location**:
   - WebUI static files are located at `frontend/` (`c:\Users\ddat2\Downloads\Projects\pyvideotrans\frontend\`).
   - Served in `webui.py` (lines 1078–1080) via `app.router.add_static("/css", FRONTEND_DIR / "css")`, `/js`, and `/assets`.
   - Entry point: `frontend/index.html` loads `<script type="module" src="./js/app.js"></script>`.
2. **Current Stage 3 Implementation**:
   - File: `frontend/js/screens/Stage3VoiceDubbing.js` (279 lines).
   - Currently contains placeholder UI with hardcoded speaker profiles for Alex Carter and Elena Rostova (lines 86–109), dummy tabs ("Dubbing", "Voices", "Glossary"), static tone mode buttons, and mock teleprompter blocks using `<input>` (lines 238–242).
   - Missing: TTS provider dropdown, dynamic `/api/voices` voice loading, dynamic speaker-to-voice matrix, per-block `voiceOverride`, and "Reset to Default" button.
3. **Reactive Store Architecture**:
   - File: `frontend/js/state.js` (`window.dubDubStore`).
   - `state.backend.options.voices`: Contains `[[0, "ElevenLabs"], [1, "OmniVoice(Built-in)"], [2, "VieNeu-TTS"], [3, "Gemini TTS"]]` returned by `GET /api/options`.
   - `loadVoices()` (lines 513–526): Calls `GET /api/voices?ttsType=${config.ttsType}&language=${targetLang}` and populates `state.backend.options.voiceRoles`.
   - `syncPreviewPlayback(media)` (lines 298–334): Synchronizes video playback with HUD timecodes, scrubber, and active segment card styles directly on `timeupdate` without calling `this.notify()` to preserve continuous `<video>` playback.
   - Missing in store: `state.speakerVoiceMap`, `updateSpeakerVoice()`, `setSegmentVoiceOverride()`, `clearSegmentVoiceOverride()`, `updateSegmentTargetText()`, and canvas subtitle DOM updates in `syncPreviewPlayback()`.
4. **Video Canvas Subtitle Bar**:
   - File: `frontend/js/components/VideoPlayer.js` (lines 224–248).
   - Currently renders subtitle container without queryable data attributes (`data-canvas-subtitle`, `data-canvas-speaker-badge`).

---

## 2. Logic Chain

1. **R1 (TTS Provider & Voice Discovery Console)**:
   - `GET /api/options` already provides the 4 supported TTS providers in `options.voices`.
   - Binding the provider dropdown in Stage 3 to `state.backend.config.ttsType` and triggering `updateBackendConfig('ttsType', value)` ensures `loadVoices()` is called whenever provider changes.
   - Populating the voice dropdown from `state.backend.options.voiceRoles` ensures voices dynamically reflect the selected provider and `targetLanguage`.
2. **R2 (Global Speaker-to-Voice Mapping Matrix)**:
   - `state.segments` contains speaker identifiers (`speakerId`, `speakerName`, `speakerCode`, `speakerColor`).
   - Extracting distinct speakers dynamically allows rendering an assignment row for each speaker.
   - Storing mappings in `state.speakerVoiceMap` ensures persistence across stage transitions (1 -> 2 -> 3 -> 4).
   - Resolving block voices as `seg.voiceOverride || state.speakerVoiceMap[speakerId] || defaultVoice` ensures global voice changes propagate instantly to all non-overridden blocks without expensive manual segment iteration.
3. **R3 (Translated Dialog Blocks with Overrides)**:
   - Using `<textarea rows="2" data-segment-input="stage3-${seg.id}">` ensures multiline text editing and allows `app.js` lines 19–23 and 55–63 to restore selection and focus across state notifications.
   - Timestamp formatting with `store.formatTime(seg.startSec)` produces exact `MM:SS.mmm` timecodes.
   - Voice dropdown with `(Default)` indicator and conditional "Reset to Default" button provides intuitive override workflow.
4. **R4 (Video Preview Subtitle Overlay & Synchronized Playback)**:
   - Adding `data-canvas-subtitle` and `data-canvas-speaker-badge` to `VideoPlayer.js` allows `syncPreviewPlayback()` in `state.js` to update text and badge directly at 60fps during playback without calling `notify()`.
   - Card click and audition button invoking `seekAndPlay(seg.startSec, seg.id)` starts smooth continuous video playback.

---

## 3. Caveats

1. **No External Live Services Required**:
   - VieNeu-TTS, OmniVoice, Gemini TTS, and ElevenLabs voice catalogs are handled either via cached JSON or fallback lists (`["No", ...]`) in `videotrans/util/help_role.py`. Third-party API keys are not required for voice discovery to function.
2. **Video Fallback**:
   - When no source video is ingested, `VideoPlayer.js` renders a static preview image (`assets/screen_2_broadcast_split.png`). Subtitle and HUD elements must render cleanly in both video and image fallback modes.
3. **Focus Preservation Discipline**:
   - Modifying `targetText` must use `data-segment-input` and avoid tearing down DOM on every keystroke (`updateSegmentTargetText` should only notify on blur/change or update DOM subtitle directly).

---

## 4. Conclusion

- The implementation of Stage 3 (R1–R4) requires modifications to:
  1. `frontend/js/state.js`
  2. `frontend/js/screens/Stage3VoiceDubbing.js`
  3. `frontend/js/components/VideoPlayer.js`
- Automated tests should be created in `tests/test_stage3_voice_dubbing.py` verifying state mapping, override logic, backend `/api/voices` responses, and frontend component markup invariants.
- Detailed implementation specifications and code templates are documented in `c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_fe\report.md`.

---

## 5. Verification Method

To independently verify findings:
1. Run existing test suite:
   ```bash
   uv run pytest tests/test_staged_asr_and_transcript.py -k "frontend"
   uv run pytest tests/test_webui.py -k "frontend"
   ```
2. Verify static frontend routes in `webui.py`:
   Inspect lines 1062–1081 in `webui.py`.
3. Inspect `frontend/js/state.js` lines 513–526 (`loadVoices`) and lines 298–334 (`syncPreviewPlayback`).
4. Inspect `frontend/js/screens/Stage3VoiceDubbing.js` lines 1–279.
