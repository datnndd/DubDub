# Project: DubDub AI Video Dubbing Studio - Stage 3: Voice & Dubbing

## Architecture
Stage 3 ("Voice & Dubbing") connects transcription (Stage 2) with audio generation and rendering (Stage 4).
The architectural components consist of:
1. **Backend TTS & Voice Catalog Router** (`webui.py`):
   - Exposes `/api/voices` querying `videotrans/util/help_role.py:role_menu()` for the 4 contiguous providers (ElevenLabs, OmniVoice, VieNeu-TTS, Gemini TTS).
   - Serves provider options via `/api/options`.
2. **Frontend Reactive Store** (`frontend/js/state.js`):
   - Single source of truth (`window.dubDubStore`).
   - Maintains `state.speakerVoiceMap`, `state.segments` (with `targetText`, `voiceOverride`), and `state.backend.config.ttsType`.
   - Provides methods for voice discovery, speaker voice mapping, per-block overrides, and canvas subtitle DOM synchronization.
3. **Stage 3 View Screen** (`frontend/js/screens/Stage3VoiceDubbing.js`):
   - Upper-right Voice Casting console: TTS provider selection + dynamic speaker assignment matrix.
   - Teleprompter Feed: sequential translated dialog blocks with `MM:SS.mmm` timecodes, speaker badges, editable `targetText` textareas, voice dropdowns with default indicators, and "Reset to Default" buttons.
   - Card click and audition action: triggers video seek to `startSec` and continuous playback.
4. **Video Preview Player** (`frontend/js/components/VideoPlayer.js`):
   - Renders video canvas with bottom subtitle bar carrying `data-canvas-subtitle` and `data-canvas-speaker-badge`.
   - Updated at 60fps by `syncPreviewPlayback` without full DOM teardown.
5. **E2E & Unit Test Harness** (`tests/test_stage3_voice_dubbing.py`):
   - Comprehensive test suite covering backend endpoints, store logic, and frontend component contracts.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | Dedicated TTS Provider & Voice Discovery Console | Provider selector in Stage 3 dynamically fetching voices via `/api/voices` for provider and target language, synced with `dubDubStore` | M1 | ORIGINAL_REQUEST §R1 |
| F2 | Global Speaker-to-Voice Mapping Matrix | Detect distinct speakers from `state.segments`, assign voices per speaker, propagate to non-overridden blocks, persist in `state.speakerVoiceMap` | M2 | ORIGINAL_REQUEST §R2 |
| F3 | Translated Dialog Blocks with Voice Overrides & Reset | Formatted `MM:SS.mmm` timestamps, speaker badge, editable `targetText`, selected voice dropdown, per-block `voiceOverride`, and "Reset to Default" button | M3 | ORIGINAL_REQUEST §R3 |
| F4 | Video Preview Subtitle Overlay & Synchronized Playback | Clicking dialog block seeks to `startSec` and plays continuously; canvas bottom subtitle bar displays active `targetText` with speaker badge synced with playhead/HUD | M4 | ORIGINAL_REQUEST §R4 |
| F5 | Comprehensive Automated Test Suite | Automated tests in `tests/test_stage3_voice_dubbing.py` passing with `uv run pytest` | M5 | ORIGINAL_REQUEST §Verification |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Backend Voice API & Store Foundation | Ensure `/api/voices` is resilient, implement `speakerVoiceMap`, distinct speaker extraction, and voice loading in `state.js` | none | DONE |
| M2 | Dynamic Voice Casting Console & Speaker Matrix | Implement upper Voice Casting console in `Stage3VoiceDubbing.js` with TTS provider dropdown and speaker-to-voice matrix | M1 | DONE |
| M3 | Teleprompter Dialog Blocks, Overrides & Text Editing | Implement translated dialog blocks in `Stage3VoiceDubbing.js` with `MM:SS.mmm` timecodes, editable `targetText`, voice selector, `voiceOverride`, and reset button | M2 | DONE |
| M4 | Subtitle Overlay & Video Playback Synchronization | Add queryable attributes in `VideoPlayer.js`, implement real-time canvas subtitle rendering in `state.js`, and seek-and-play click handlers | M3 | DONE |
| M5 | Automated Test Suite & E2E Verification | Create `tests/test_stage3_voice_dubbing.py` with 20+ tests covering endpoints, store logic, UI contracts, and run full test suite | M1, M2, M3, M4 | DONE |

## Interface Contracts

### Backend `/api/voices`
- Request: `GET /api/voices?ttsType={int}&language={str}` (also accepting `provider` / `target_language` aliases)
- Response: `{"voices": list[str]}` (e.g. `["No", "Minh Đức", ...]`)

### Store State (`window.dubDubStore.state`)
- `state.speakerVoiceMap`: `Record<string, string>` (e.g. `{"speaker-1": "Minh Đức", "speaker-2": "Thái Sơn"}`)
- `state.segments[i]`:
  - `id`: string/int
  - `speakerId`: string
  - `speakerName`: string
  - `speakerColor`: string
  - `startSec`: float
  - `endSec`: float
  - `sourceText`: string
  - `targetText`: string (translated text)
  - `voiceOverride`: string | null (per-block override)
- Store Actions:
  - `updateSpeakerVoice(speakerId: string, voice: string): void`
  - `setSegmentVoiceOverride(segmentId: string, voice: string): void`
  - `clearSegmentVoiceOverride(segmentId: string): void`
  - `updateSegmentTargetText(segmentId: string, targetText: string): void`
  - `getResolvedVoice(segment: object): string`
  - `seekAndPlay(startSec: number, segmentId: string): void`

### DOM Query Attributes for VideoPlayer & Stage 3
- Video canvas subtitle: `[data-canvas-subtitle]`
- Video canvas speaker badge: `[data-canvas-speaker-badge]`
- Stage 3 provider select: `[data-action="select-tts-provider"]`
- Speaker voice mapping select: `[data-speaker-voice-select="{speakerId}"]`
- Segment targetText editor: `[data-segment-input="stage3-{segmentId}"]`
- Segment voice override select: `[data-segment-voice-select="{segmentId}"]`
- Segment reset voice button: `[data-action="reset-segment-voice"][data-segment-id="{segmentId}"]`
- Segment card seek action: `[data-action="seek-segment"][data-segment-id="{segmentId}"]`

## Code Layout
- `webui.py`: Backend server, API routes (`/api/voices`, `/api/options`).
- `frontend/js/state.js`: Core reactive store, state mutations, playback sync.
- `frontend/js/screens/Stage3VoiceDubbing.js`: Stage 3 screen component (Voice Casting console + Teleprompter feed).
- `frontend/js/components/VideoPlayer.js`: Video player with HUD and bottom canvas subtitle bar.
- `tests/test_stage3_voice_dubbing.py`: Stage 3 automated test suite.
