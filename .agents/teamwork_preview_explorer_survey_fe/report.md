# Frontend Architecture Exploration Report: DubDub Stage 3 (Voice & Dubbing)

**Project:** DubDub AI Video Dubbing Studio — Stage 3: Voice & Dubbing  
**Explorer:** Frontend Architecture Explorer  
**Date:** 2026-09-19  
**Status:** Investigation Complete — Ready for Implementation  

---

## 1. Executive Summary

This investigation analyzed the frontend codebase for DubDub AI Video Dubbing Studio to determine the exact architectural requirements, existing code assets, state store interactions, and implementation plan for **Stage 3: Voice & Dubbing** (Requirements R1–R4).

### Key Architectural Discoveries:
1. **Frontend Directory Layout**:
   - The WebUI frontend is served from `frontend/` (not `pyvideotrans/webui/static/`). In `webui.py` (lines 1078–1080), static routes are mounted to `/css`, `/js`, and `/assets` pointing directly to `ROOT_DIR / "frontend"`.
   - The reactive store lives in `frontend/js/state.js`, exported as `export const store = new WorkflowStore();` and attached globally as `window.dubDubStore = store;`.
   - The application coordinator is `frontend/js/app.js`, which subscribes to store notifications and calls `renderApp()`. It features focus-restoration logic targeting elements with `data-segment-input`.
2. **Current State of Stage 3 (`frontend/js/screens/Stage3VoiceDubbing.js`)**:
   - Currently contains placeholder UI: dummy navigation pill tabs ("Dubbing", "Voices", "Glossary"), hardcoded speaker profiles for "Alex Carter" and "Elena Rostova", a static tone mode button grid, and mock teleprompter blocks with single-line `<input>` fields labeled `AI DUB (ES)`.
   - It **completely lacks**:
     - Dynamic TTS provider selection (ElevenLabs, OmniVoice, VieNeu-TTS, Gemini TTS).
     - Dynamic voice role fetching via `/api/voices`.
     - Reactive Speaker-to-Voice mapping matrix.
     - Per-block voice override mechanism and "Reset to Default" action.
     - Synchronized canvas subtitle rendering during continuous playback.
3. **Backend API Readiness**:
   - `GET /api/options`: Returns supported TTS providers in `voices: list(enumerate(tts.TTS_NAME_LIST))` (0: ElevenLabs, 1: OmniVoice(Built-in), 2: VieNeu-TTS, 3: Gemini TTS) and defaults (`ttsType: 2`).
   - `GET /api/voices?ttsType={ttsType}&language={language}`: Fully implemented in `webui.py` (line 681) using `role_menu(tts_type, langcode=language)`, returning `{"voices": [...]}`.
   - `POST /api/jobs`: Accepts `ttsType`, `voiceRole`, `targetLanguage`, and existing parameters.

---

## 2. Directory Layout & Component Hierarchy

```
frontend/
├── index.html                   # Mount point (<div id="app">), Tailwind config, theme tokens
├── css/
│   └── styles.css               # Range sliders, pulse animations, custom scrollbars
├── js/
│   ├── app.js                   # Application coordinator & activeElement focus restoration
│   ├── state.js                 # Central WorkflowStore singleton (`window.dubDubStore`)
│   ├── components/
│   │   ├── Header.js            # DubDub brand, step indicator, GPU status
│   │   ├── WorkflowStepper.js   # 4-stage stepper (Prepare -> Review -> Voice -> Edit)
│   │   ├── VideoPlayer.js       # Reusable video canvas, HUD telemetry, subtitle overlay
│   │   ├── WaveformScrubber.js  # Audio stem waveform scrubber & transport deck
│   │   ├── StatusFooter.js      # Bottom action bar (step CTA, job progress)
│   │   └── TranslationConfig.js # Shared LLM Translation configuration deck
│   └── screens/
│       ├── Stage1Prepare.js     # Media ingest, ASR/translation options, "Start Dub"
│       ├── Stage2ReviewTranscript.js # Transcript cards, inline edit, split, OCR replace
│       ├── Stage3VoiceDubbing.js     # [TARGET] Voice casting, speaker mapping, teleprompter
│       └── Stage4EditVideo.js        # Timeline NLE & 4K export deck
```

---

## 3. Reactive State Store (`frontend/js/state.js`) Deep-Dive

### Existing Relevant State Keys (`WorkflowStore.state`)

| State Path | Type | Current Purpose | Required Changes for Stage 3 |
| :--- | :--- | :--- | :--- |
| `currentStep` | `number` | Active workflow step (1, 2, 3, 4) | None (Stage 3 is step `3`) |
| `activeSegmentId` | `number \| string` | Currently highlighted/playing segment | Used to highlight active card & sync preview subtitle |
| `playback.currentTime` | `number` | Current playhead in seconds | Synchronized via `syncPreviewPlayback` |
| `playback.formattedTime` | `string` | Current timecode `MM:SS.mmm` | Synchronized via `formatTime` |
| `playback.isPlaying` | `boolean` | Video play/pause state | Toggled by `togglePlay()` / `seekAndPlay()` |
| `languages.source` | `object` | `{ code, name, flag, autoDetected }` | Source speech language |
| `languages.target` | `object` | `{ code, name }` | Target dubbed language; triggers `loadVoices()` when changed |
| `engines.speakerDiarization` | `boolean` | Whether speaker diarization was enabled | Distinguishes multi-speaker vs single-speaker badge styling |
| `segments` | `Array<object>` | List of dialogue segments | Each segment must support `targetText` & `voiceOverride` |
| `backend.config.ttsType` | `number` | Selected TTS provider index (0..3) | Synchronized with Stage 3 provider selector |
| `backend.config.voiceRole` | `string` | Global selected voice role name | Synchronized with Stage 3 voice discovery |
| `backend.options.voices` | `Array<[number, string]>` | Available TTS providers from `/api/options` | `[[0, "ElevenLabs"], [1, "OmniVoice"], ...]` |
| `backend.options.voiceRoles` | `Array<string>` | Loaded voice names from `/api/voices` | Stored dynamically when `loadVoices()` resolves |
| **`speakerVoiceMap`** | **`object`** | **Missing in state** | **Add to state**: maps speaker ID/key to assigned voice name |

### Segment Object Structure in `state.segments`

Existing properties:
```javascript
{
  id: 1,
  speakerId: "spk_1",
  speakerName: "Alex Carter",
  speakerCode: "AC",
  speakerColor: "amber",
  startSec: 81.0,
  endSec: 86.4,
  startTime: "01:21.000",
  endTime: "01:26.400",
  cps: 14.2,
  cpsStatus: "Optimal",
  sourceText: "We are entering an era...",
  targetText: "Estamos entrando en una era...",
  voiceOverride: undefined // Needs explicit support in Stage 3
}
```

### Store Mutations: Existing vs Required

1. **Existing Methods**:
   - `setStep(step)`: Navigates between stages 1..4.
   - `updateTargetLanguage(code, name)`: Updates `state.languages.target`, calls `loadVoices()`, calls `notify()`.
   - `updateBackendConfig(field, value)`: Updates backend config; if `field === 'ttsType'`, calls `loadVoices()`.
   - `loadVoices()`: Fetches `/api/voices?ttsType=${config.ttsType}&language=${targetLang}`, sets `options.voiceRoles`, defaults `config.voiceRole`.
   - `seekAndPlay(seconds, segmentId)`: Sets `currentTime`, sets `activeSegmentId`, seeks `<video>` to `seconds`, invokes `play()`, and triggers `syncPreviewPlayback`.
   - `syncPreviewPlayback(media)`: Runs on `ontimeupdate`, updates timecode nodes, timeline, scrubber progress, and `[data-segment-card]` active styling. Note: deliberately does **not** call `this.notify()` to prevent destroying `<video>` DOM during continuous playback.
   - `formatTime(seconds)`: Formats float seconds into `MM:SS.mmm`.

2. **Required Store Extensions**:
   - **`speakerVoiceMap` initialization**:
     Add `speakerVoiceMap: {}` to initial `this.state`.
   - **`updateSpeakerVoice(speakerId, voice)`**:
     Updates `state.speakerVoiceMap[speakerId] = voice`. Replaces assigned voice for that speaker across all blocks that do not have `voiceOverride`. Calls `notify()`.
   - **`setSegmentVoiceOverride(segmentId, voice)`**:
     Sets `seg.voiceOverride = voice`. If `voice === ''` or equals the speaker's assigned default, removes/nullifies `voiceOverride`. Calls `notify()`.
   - **`clearSegmentVoiceOverride(segmentId)`**:
     Sets `seg.voiceOverride = null` (or deletes the key). Calls `notify()`.
   - **`updateSegmentTargetText(id, text, forceNotify = false)`**:
     Sets `seg.targetText = text`. If user is typing in `data-segment-input="stage3-${id}"`, avoids full re-render on each keystroke (preserving cursor position). If `id === activeSegmentId`, immediately updates `[data-canvas-subtitle]` in DOM.
   - **`loadVoices()` hardening**:
     When voices finish loading, if `speakerVoiceMap` is empty or has orphaned voices, automatically assign the default voice (`config.voiceRole` or `voiceRoles[0]`) to all detected speakers in `state.segments`.
   - **`syncPreviewPlayback(media)` extension**:
     In addition to updating `data-segment-card`, directly update:
     - `[data-canvas-subtitle]` with `currentActive.targetText || currentActive.sourceText || ''`.
     - `[data-canvas-speaker-badge]` with `currentActive.speakerName || currentActive.speakerLabel || 'Speaker 1'`.

---

## 4. Video Player & Canvas Subtitle Overlay Investigation

### Reusable `VideoPlayer.js` Mechanics
- Video element: `<video data-source-preview class="w-full h-full object-contain bg-black" src="${previewUrl}" controls ...>`
- Subtitle Bar (lines 224–248):
  - Currently renders a static container based on `subtitleVariant === 'dual'`.
  - Displays `currentSegment.targetText || currentSegment.sourceText || ''`.
- **Identified Gap for R4**:
  - The subtitle elements lack dedicated queryable data attributes (`data-canvas-subtitle`, `data-canvas-speaker-badge`).
  - Because `syncPreviewPlayback` runs on `ontimeupdate` without calling `this.notify()`, the canvas subtitle does not currently update as the video progresses between segments unless targeted DOM manipulation is added to `syncPreviewPlayback`.

### Synchronized Seeking & Continuous Playback
- Calling `window.dubDubStore.seekAndPlay(seg.startSec, seg.id)`:
  - Sets `state.playback.currentTime = seg.startSec`.
  - Sets `state.activeSegmentId = seg.id`.
  - Seeks `<video data-source-preview>.currentTime = seg.startSec`.
  - Calls `<video>.play()`.
  - Updates `state.playback.isPlaying = true`.
  - Triggers `syncPreviewPlayback(media)`, which updates playhead HUD, scrubber progress, segment card highlight, and canvas subtitle.
- Clicking any segment block in Stage 3 or clicking its audition button must call `seekAndPlay(seg.startSec, seg.id)`.

---

## 5. Detailed Analysis by Requirement (R1–R4)

### R1. Dedicated TTS Provider & Voice Discovery Console in `Stage3VoiceDubbing.js`

#### Requirements
- Voice configuration console in upper-right deck (5 cols) of Stage 3.
- Allow selecting any supported TTS provider: ElevenLabs, OmniVoice, VieNeu-TTS, Gemini TTS.
- Changing provider must dynamically fetch and populate voices from `/api/voices?ttsType={id}&language={lang}`.
- Keep current selected voice and provider in `window.dubDubStore` synced with Stage 1 and downstream stages.

#### Existing vs Required
- **Existing**:
  - `webui.py` supports `/api/options` (returns providers 0..3) and `/api/voices`.
  - `state.backend.options.voices`: contains `[[0, "ElevenLabs"], [1, "OmniVoice(Built-in)"], [2, "VieNeu-TTS"], [3, "Gemini TTS"]]`.
  - `state.backend.config.ttsType` and `state.backend.config.voiceRole` exist.
  - `loadVoices()` exists in `state.js`.
- **Needs Creation/Update**:
  - In `Stage3VoiceDubbing.js`, replace dummy "Synthesis Engine v4.2" header and static tab bar with the **TTS Provider & Voice Discovery Console**.
  - Provider Dropdown:
    ```html
    <select class="..." onchange="window.dubDubStore.updateBackendConfig('ttsType', Number(this.value))">
      ${backend.options.voices.map(([typeId, label]) => `
        <option value="${typeId}" ${backend.config.ttsType === typeId ? 'selected' : ''}>${label}</option>
      `).join('')}
    </select>
    ```
  - Global Default Voice Dropdown:
    ```html
    <select class="..." onchange="window.dubDubStore.updateBackendConfig('voiceRole', this.value)">
      ${(backend.options.voiceRoles || ['No']).map(voice => `
        <option value="${voice}" ${backend.config.voiceRole === voice ? 'selected' : ''}>${voice}</option>
      `).join('')}
    </select>
    ```
  - Target Language Quick Switcher:
    Allows user to switch `targetLanguage` directly within Stage 3, triggering `updateTargetLanguage(code, name)`, which in turn calls `loadVoices()`.

---

### R2. Global Speaker-to-Voice Mapping Matrix

#### Requirements
- Dynamically detect all distinct speakers from `state.segments`.
- Render an assignment control for each detected speaker with speaker badge and voice dropdown.
- Assigning a voice to Speaker X must immediately update all dialog blocks belonging to Speaker X that do not have an explicit per-block override.
- Maintain mapping in `state.speakerVoiceMap` across stage navigation.

#### Existing vs Required
- **Existing**:
  - Speaker metadata in `state.segments`: `speakerId`, `speakerName`, `speakerCode`, `speakerColor`.
- **Needs Creation/Update**:
  - Add `speakerVoiceMap: {}` to `state.js` initial state.
  - Distinct speaker extraction logic:
    ```javascript
    function getDistinctSpeakers(segments, stateSpeakers, diarizationEnabled) {
      const distinctKeys = Array.from(new Set(
        segments.map(s => s.speakerId || s.speakerLabel || s.speakerName || s.speaker).filter(Boolean)
      ));
      const multi = diarizationEnabled && distinctKeys.length > 1;
      if (!multi && distinctKeys.length <= 1) {
        return [{ id: 'spk_1', name: 'Speaker 1', code: 'S1', color: 'amber', isSingle: true }];
      }
      return distinctKeys.map((key, idx) => {
        const seg = segments.find(s => (s.speakerId || s.speakerLabel || s.speakerName || s.speaker) === key);
        const meta = (stateSpeakers || []).find(sp => sp.id === key) || {};
        return {
          id: key,
          name: seg.speakerName || seg.speakerLabel || meta.name || `Speaker ${idx + 1}`,
          code: seg.speakerCode || meta.code || `S${idx + 1}`,
          color: seg.speakerColor || meta.color || ['amber', 'secondary', 'emerald', 'rose', 'purple'][idx % 5],
          isSingle: false
        };
      });
    }
    ```
  - In `WorkflowStore`:
    ```javascript
    updateSpeakerVoice(speakerId, voice) {
      if (!this.state.speakerVoiceMap) this.state.speakerVoiceMap = {};
      this.state.speakerVoiceMap[speakerId] = voice;
      this.notify();
    }
    ```
  - In Voice Casting UI:
    Render a list of speaker rows, each containing the speaker badge and a `<select onchange="window.dubDubStore.updateSpeakerVoice('${speaker.id}', this.value)">` populated with `voiceRoles`.

---

### R3. Translated Dialog Blocks with Per-Block Voice Overrides

#### Requirements
- In Stage 3 teleprompter feed:
  1. Start/end timestamps formatted as `MM:SS.mmm`.
  2. Speaker identifier / badge matching Stage 2 styling.
  3. Inline editable textarea for `seg.targetText` updating the reactive store on edit.
  4. Voice selector showing the speaker's assigned default (e.g. `Voice A (Default)`).
- Allow per-block voice override via dropdown, visually indicating the override.
- "Reset to Default" button on overridden blocks to clear the override.
- Changing global speaker voice updates all blocks for that speaker except those with per-block override.

#### Existing vs Required
- **Existing**:
  - Stage 3 currently has a static teleprompter with `<input>` and hardcoded voices.
- **Needs Creation/Update**:
  - Update `renderStage3VoiceDubbing(state)`:
    - Format timestamps: `${store.formatTime(seg.startSec)} ➔ ${store.formatTime(seg.endSec)}`.
    - Speaker badge: reuse Stage 2 `speakerColorClasses` and `speakerDotBg` mapping.
    - Editable textarea:
      ```html
      <textarea
        rows="2"
        data-segment-input="stage3-${escapeHtml(seg.id)}"
        class="w-full bg-white border border-stone-200 focus:border-[#8D4B00] focus:ring-1 focus:ring-[#8D4B00] rounded-lg p-2 text-xs text-stone-900 font-medium resize-none leading-relaxed"
        onclick="event.stopPropagation()"
        onfocus="window.dubDubStore.setActiveEditor(${safeId}, this.selectionStart)"
        onblur="setTimeout(() => { if (window.dubDubStore.activeEditor && String(window.dubDubStore.activeEditor.segmentId) === String(${safeId})) window.dubDubStore.clearActiveEditor(${safeId}); }, 250); window.dubDubStore.updateSegmentTargetText(${safeId}, this.value, true);"
        oninput="window.dubDubStore.updateSegmentTargetText(${safeId}, this.value)"
        onchange="window.dubDubStore.updateSegmentTargetText(${safeId}, this.value, true)"
      >${escapeHtml(seg.targetText || '')}</textarea>
      ```
    - Voice Selector with Override Logic:
      - Speaker default: `const globalVoice = state.speakerVoiceMap?.[speakerId] || backend.config.voiceRole || voiceRoles[0];`
      - Current block voice: `const activeVoice = seg.voiceOverride || globalVoice;`
      - Is overridden: `const isOverridden = Boolean(seg.voiceOverride && seg.voiceOverride !== globalVoice);`
      - Dropdown rendering:
        ```html
        <select 
          class="bg-white border ${isOverridden ? 'border-[#8D4B00] ring-1 ring-[#8D4B00] text-[#8D4B00]' : 'border-stone-200 text-stone-800'} text-[10px] font-bold rounded-lg px-2 py-1 focus:outline-none"
          onclick="event.stopPropagation()"
          onchange="window.dubDubStore.setSegmentVoiceOverride(${safeId}, this.value)">
          ${voiceRoles.map(v => `
            <option value="${v}" ${v === activeVoice ? 'selected' : ''}>
              ${v}${v === globalVoice ? ' (Default)' : ''}
            </option>
          `).join('')}
        </select>
        ```
      - Reset to Default button:
        ```html
        ${isOverridden ? `
          <button 
            class="px-2 py-1 rounded bg-amber-50 hover:bg-amber-100 text-[#8D4B00] border border-amber-200 text-[9px] font-bold flex items-center gap-0.5 shadow-2xs"
            title="Reset to speaker default voice (${globalVoice})"
            onclick="event.stopPropagation(); window.dubDubStore.clearSegmentVoiceOverride(${safeId})">
            <span class="material-symbols-outlined text-[10px]">restart_alt</span>
            <span>Reset</span>
          </button>
        ` : ''}
        ```
    - In `state.js`:
      ```javascript
      setSegmentVoiceOverride(segmentId, voice) {
        const seg = this.state.segments.find(s => String(s.id) === String(segmentId));
        if (!seg) return;
        const speakerKey = seg.speakerId || seg.speakerLabel || seg.speakerName || 'spk_1';
        const globalVoice = this.state.speakerVoiceMap?.[speakerKey] || this.state.backend.config.voiceRole;
        if (!voice || voice === globalVoice) {
          delete seg.voiceOverride;
        } else {
          seg.voiceOverride = voice;
        }
        this.notify();
      }

      clearSegmentVoiceOverride(segmentId) {
        const seg = this.state.segments.find(s => String(s.id) === String(segmentId));
        if (seg) {
          delete seg.voiceOverride;
          this.notify();
        }
      }
      ```

---

### R4. Video Preview Subtitle Overlay & Synchronized Playback

#### Requirements
- Display translated subtitle text for the currently active/playing segment directly on the video canvas bottom subtitle bar.
- Clicking any translated dialog block seeks video player to `startSec` and begins continuous playback.
- HUD timecode and scrubber stay synchronized; canvas subtitle dynamically matches the segment at `currentTime`.

#### Existing vs Required
- **Existing**:
  - `seekAndPlay(seconds, segmentId)` exists in `state.js`.
  - `syncPreviewPlayback(media)` synchronizes timecode, timeline, scrubber, and card active states.
  - VideoPlayer renders a subtitle container over the canvas.
- **Needs Creation/Update**:
  1. Teleprompter card click:
     - Wrap dialog card in:
       ```html
       <div 
         data-segment-card="${escapeHtml(seg.id)}"
         class="p-2.5 rounded-xl border ${isActive ? 'border-2 border-[#8D4B00] bg-amber-50/50 shadow-xs' : 'border-stone-200 bg-white hover:border-amber-200'} shadow-2xs flex flex-col md:flex-row md:items-center gap-3 relative transition-all cursor-pointer"
         onclick="window.dubDubStore.seekAndPlay(${seg.startSec}, ${safeId})">
       ```
     - Prevent propagation on inner interactive elements (`<textarea>`, `<select>`, `<button>`).
  2. Canvas Subtitle Elements in `VideoPlayer.js`:
     ```html
     <!-- Bottom Subtitle Bar Over Canvas -->
     <div class="absolute inset-x-3 bottom-2 z-20 flex justify-center text-center pointer-events-none">
       <div class="w-full max-w-xl bg-black/85 backdrop-blur-md px-3.5 py-1.5 rounded-lg border border-amber-500/30 shadow-xl flex flex-col items-center">
         <div class="flex items-center gap-1.5 mb-0.5">
           <span data-canvas-speaker-badge class="px-2 py-0.2 rounded-full bg-[#8D4B00] text-white text-[8px] font-bold uppercase tracking-wider">
             ${escapeHtml(currentSegment.speakerName || currentSegment.speakerLabel || 'Speaker 1')}
           </span>
         </div>
         <p data-canvas-subtitle class="text-white font-semibold text-xs leading-snug">
           “${escapeHtml(currentSegment.targetText || currentSegment.sourceText || currentSegment.text || '')}”
         </p>
         ${currentSegment.sourceText && currentSegment.targetText ? `
           <p data-canvas-source-subtitle class="text-amber-200/90 text-[10px] font-mono mt-0.5">
             ${escapeHtml((state.languages.source.code || 'EN').toUpperCase())}: “${escapeHtml(currentSegment.sourceText)}”
           </p>
         ` : ''}
       </div>
     </div>
     ```
  3. Dynamic Subtitle Updating in `state.js`:
     In `syncPreviewPlayback(media)`:
     ```javascript
     const canvasSub = document.querySelector('[data-canvas-subtitle]');
     const canvasBadge = document.querySelector('[data-canvas-speaker-badge]');
     if (canvasSub) {
       canvasSub.textContent = currentActive
         ? (currentActive.targetText ? `“${currentActive.targetText}”` : (currentActive.text ? `“${currentActive.text}”` : ''))
         : '';
     }
     if (canvasBadge) {
       canvasBadge.textContent = currentActive
         ? (currentActive.speakerName || currentActive.speakerLabel || 'Speaker 1')
         : '';
       canvasBadge.style.display = currentActive ? 'inline-flex' : 'none';
     }
     ```
     In `updateSegmentTargetText(id, text, forceNotify)`:
     If `String(id) === String(this.state.activeSegmentId)`:
     ```javascript
     const canvasSub = document.querySelector('[data-canvas-subtitle]');
     if (canvasSub) {
       canvasSub.textContent = text ? `“${text}”` : '';
     }
     ```

---

## 6. Implementation Strategy & File Impact Matrix

| File Path | Nature of Modification | Summary of Changes |
| :--- | :--- | :--- |
| `frontend/js/state.js` | Update | Add `speakerVoiceMap` state; add methods `updateSpeakerVoice`, `setSegmentVoiceOverride`, `clearSegmentVoiceOverride`, `updateSegmentTargetText`; update `loadVoices()` to sync speaker map; update `syncPreviewPlayback` to update canvas subtitle and speaker badge. |
| `frontend/js/screens/Stage3VoiceDubbing.js` | Overwrite / Full rewrite | Replace placeholder UI with dedicated TTS provider selector, voice discovery status, global speaker-to-voice casting matrix, tuning faders, and dual-track teleprompter blocks with formatted timestamps, Stage 2 speaker badges, editable `targetText` textarea, voice dropdown with `(Default)` label, `Reset to Default` button, and card-click `seekAndPlay`. |
| `frontend/js/components/VideoPlayer.js` | Update | Enhance canvas subtitle bar to include `data-canvas-subtitle`, `data-canvas-speaker-badge`, and `data-canvas-source-subtitle`. |
| `tests/test_stage3_voice_dubbing.py` | New file | Automated pytest test suite covering requirements R1–R4, backend `/api/voices` endpoint, state logic, and frontend rendering invariants. |

---

## 7. Verification Strategy & Test Cases

Automated verification will be authored in `tests/test_stage3_voice_dubbing.py` to run via `uv run pytest`:

1. **Backend TTS & Voice Endpoints (`/api/voices`, `/api/options`)**:
   - Verify `GET /api/options` returns supported TTS providers (ElevenLabs, OmniVoice, VieNeu-TTS, Gemini TTS).
   - Verify `GET /api/voices?ttsType={ttsType}&language={lang}` returns valid voice list for each provider.
   - Verify fallback handling when provider has no third-party keys.
2. **State & Speaker-to-Voice Mapping Invariants**:
   - Verify `speakerVoiceMap` initializes and stores mappings per speaker.
   - Verify updating speaker voice updates all blocks for that speaker without overrides.
   - Verify setting `voiceOverride` on a single block preserves overrides when the speaker's global voice is updated.
   - Verify clearing `voiceOverride` restores the speaker's global voice.
   - Verify `updateSegmentTargetText` modifies `seg.targetText` and preserves `state.segments`.
3. **Frontend Component & Markup Assertions**:
   - Assert `Stage3VoiceDubbing.js` renders the TTS provider select (`ttsType`), voice discovery dropdown, speaker-to-voice matrix, formatted timestamps (`MM:SS.mmm`), Stage 2 speaker badges, `data-segment-input` textareas, per-block voice dropdowns, and "Reset" buttons.
   - Assert `VideoPlayer.js` has `data-canvas-subtitle` and `data-canvas-speaker-badge`.
   - Assert `seekAndPlay` is wired to dialog blocks and audition buttons.

---

## 8. Conclusion

The existing architecture in `frontend/js/state.js`, `frontend/js/components/VideoPlayer.js`, and `webui.py` provides a robust, proven foundation. Stage 3 can be implemented cleanly, adhering strictly to the existing reactive design system, maintaining zero regressions in Stages 1, 2, and 4, and passing 100% of automated tests.
