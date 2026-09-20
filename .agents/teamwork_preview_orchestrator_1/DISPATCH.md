## 2026-09-19T14:43:04Z

You are the Project Orchestrator for the DubDub project.
Your assigned working directory is: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_orchestrator_1
Project root: c:\Users\ddat2\Downloads\Projects\pyvideotrans

The user request is recorded in: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\ORIGINAL_REQUEST.md under header `## 2026-09-19T14:42:14Z`.

Mission:
Implement **Stage 3: Voice & Dubbing** in DubDub AI Video Dubbing Studio:
- R1. Dedicated TTS Provider & Voice Discovery Console in Stage 3 (`Stage3VoiceDubbing.js`), dynamically fetching available voices from `/api/voices` for the provider and target language, synchronized with `window.dubDubStore`.
- R2. Global Speaker-to-Voice Mapping Matrix in Voice Casting console, detecting distinct speakers from `state.segments`, assigning voices, updating all non-overridden blocks, persisting in `state.speakerVoiceMap`.
- R3. Translated Dialog Blocks with formatted start/end timestamps (`MM:SS.mmm`), speaker badge, editable translated text (`targetText`), selected voice dropdown, per-block voice overrides (`seg.voiceOverride`), and "Reset to Default" button.
- R4. Video Preview Subtitle Overlay & Synchronized Playback: clicking dialog blocks seeks to `startSec` and plays continuously, canvas bottom subtitle bar displays active segment `targetText` with speaker badge, playhead/HUD timecode sync.
- Verification: Comprehensive automated tests in `tests/test_stage3_voice_dubbing.py` (or `tests/test_webui.py`), passing with `uv run pytest`.

Please maintain your `BRIEFING.md` and `progress.md` in your working directory. Decompose into workstreams, dispatch specialist subagents (explorers, implementers, testers/reviewers), ensure high code quality, and report back when complete so victory audit can be initiated.
