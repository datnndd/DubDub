## 2026-09-19T14:43:49Z

You are the Frontend Architecture Explorer for the DubDub Stage 3: Voice & Dubbing project.
Your assigned working directory is: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_fe
Project root: c:\Users\ddat2\Downloads\Projects\pyvideotrans

Read the authoritative user request at:
c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\ORIGINAL_REQUEST.md
Specifically header ## 2026-09-19T14:42:14Z and the Stage 3 requirements R1-R4.

Investigate the frontend codebase thoroughly:
1. Examine `pyvideotrans/webui/static/js/` (and any related subdirectories or HTML files).
2. Look at how Stage 1 and Stage 2 are implemented (e.g. `Stage1*.js`, `Stage2*.js`, `Stage3VoiceDubbing.js` or whatever files currently exist).
3. Investigate the reactive state store (`window.dubDubStore`, `store.js` or similar). What state keys exist? How are `state.segments`, `state.speakerVoiceMap`, `targetLanguage`, TTS provider, etc., structured and mutated?
4. Investigate the video player, canvas subtitle rendering, seeking mechanisms, HUD / playhead synchronization, and speaker badge styling.
5. Identify what code exists vs what needs to be created or updated for:
   - R1: Dedicated TTS Provider & Voice Discovery Console in `Stage3VoiceDubbing.js`
   - R2: Global Speaker-to-Voice Mapping Matrix in Voice Casting console
   - R3: Translated Dialog Blocks with formatted timestamps (`MM:SS.mmm`), speaker badge, editable `targetText`, voice selector, per-block `voiceOverride`, and "Reset to Default" button
   - R4: Video preview subtitle overlay on canvas bottom subtitle bar & continuous synchronized playback on block click

Write a comprehensive report to `c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_fe\report.md`.
Include concrete file paths, line numbers, data structures, and recommended implementation strategy.
When complete, notify parent via send_message with the report path and summary.
