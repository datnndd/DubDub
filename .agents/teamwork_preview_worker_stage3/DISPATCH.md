## 2026-09-19T14:51:10Z

You are the Stage 3 Implementation Worker for the DubDub project.
Your assigned working directory is: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_worker_stage3
Project root: c:\Users\ddat2\Downloads\Projects\pyvideotrans

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Read the authoritative user request at:
c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\ORIGINAL_REQUEST.md
Specifically header ## 2026-09-19T14:42:14Z and the Stage 3 requirements R1-R4.

Also read:
- Project Plan & Interface Contracts: c:\Users\ddat2\Downloads\Projects\pyvideotrans\PROJECT.md
- Frontend Survey Report: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_fe\report.md
- Backend Survey Report: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_be\report.md

Your exclusive write ownership:
1. `c:\Users\ddat2\Downloads\Projects\pyvideotrans\webui.py`
2. `c:\Users\ddat2\Downloads\Projects\pyvideotrans\frontend\js\state.js`
3. `c:\Users\ddat2\Downloads\Projects\pyvideotrans\frontend\js\screens\Stage3VoiceDubbing.js`
4. `c:\Users\ddat2\Downloads\Projects\pyvideotrans\frontend\js\components\VideoPlayer.js`
Do NOT modify test files (owned by test writer).

Implementation Requirements:
1. Backend (`webui.py`):
   - In `voices_handler`, ensure `/api/voices` accepts `ttsType` (integer index or string integer) or `provider` (alias), and `language` (or `target_language` alias).
   - Ensure clean error handling returning `{"voices": ["No"]}` if provider raises.
2. Store (`frontend/js/state.js`):
   - Initialize `state.speakerVoiceMap = {}`.
   - Implement `getDistinctSpeakers()` to detect distinct speakers from `state.segments` (`speakerId`, `speakerName`, `speakerColor`, `speakerCode`).
   - Implement `updateSpeakerVoice(speakerId, voice)`: updates `state.speakerVoiceMap[speakerId]` and notifies.
   - Implement `setSegmentVoiceOverride(segmentId, voice)`: sets `seg.voiceOverride = voice` on segment and notifies.
   - Implement `clearSegmentVoiceOverride(segmentId)`: deletes/clears `seg.voiceOverride` on segment and notifies.
   - Implement `updateSegmentTargetText(segmentId, targetText)`: updates segment's `targetText` in store.
   - Implement `getResolvedVoice(segment)`: returns `seg.voiceOverride || (this.state.speakerVoiceMap && this.state.speakerVoiceMap[seg.speakerId]) || (this.state.backend.options.voiceRoles && this.state.backend.options.voiceRoles[0]) || 'default'`.
   - In `syncPreviewPlayback(media)`: update video canvas subtitle DOM (`[data-canvas-subtitle]` and `[data-canvas-speaker-badge]`) dynamically at 60fps with active segment's `targetText` and speaker badge.
   - Ensure `state.speakerVoiceMap` persists across stage navigation.
3. Video Player (`frontend/js/components/VideoPlayer.js`):
   - Add `data-canvas-subtitle` and `data-canvas-speaker-badge` attributes to the subtitle container in the video preview overlay.
   - Render active segment's `targetText` (and speaker badge) cleanly.
4. Stage 3 Screen (`frontend/js/screens/Stage3VoiceDubbing.js`):
   - Remove dummy placeholder speaker profiles.
   - Upper Voice Casting Console:
     * TTS Provider dropdown (`data-action="select-tts-provider"`): options from `state.backend.options.voices` (ElevenLabs, OmniVoice, VieNeu-TTS, Gemini TTS), synchronized with `state.backend.config.ttsType`. On change, calls `store.updateBackendConfig('ttsType', value)` and reloads voices.
     * Dynamic Speaker Matrix: for each distinct speaker detected from `state.segments`, display their badge/name and a voice selection dropdown (`data-speaker-voice-select="${speaker.speakerId}"`) populated from `state.backend.options.voiceRoles`. On change, calls `store.updateSpeakerVoice(speaker.speakerId, e.target.value)`.
   - Teleprompter Feed (Translated Dialog Blocks):
     * Renders each segment from `state.segments`:
       - Formatted start and end timestamps (`MM:SS.mmm`) using `store.formatTime(seg.startSec)` and `store.formatTime(seg.endSec)`.
       - Speaker badge with `seg.speakerName` and `seg.speakerColor`.
       - Inline editable textarea for `seg.targetText` with `data-segment-input="stage3-${seg.id}"`, updating store via `store.updateSegmentTargetText(seg.id, e.target.value)`.
       - Voice selector dropdown (`data-segment-voice-select="${seg.id}"`): lists available voices. If not overridden, displays speaker's assigned default marked as `(Default)`. If overridden, marks as override. On change, calls `store.setSegmentVoiceOverride(seg.id, e.target.value)`.
       - "Reset to Default" button (`data-action="reset-segment-voice"`): visible only when `seg.voiceOverride != null`, clicking calls `store.clearSegmentVoiceOverride(seg.id)`.
     * Card click and Audition button (`data-action="seek-segment"`): clicking calls `store.seekAndPlay(seg.startSec, seg.id)` to seek video and play continuously.
5. Verification:
   - Run `uv run pytest` to ensure all existing tests pass and no regressions are introduced.
   - Write handoff report to `c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_worker_stage3\handoff.md`.
   - Notify parent via send_message when complete.
