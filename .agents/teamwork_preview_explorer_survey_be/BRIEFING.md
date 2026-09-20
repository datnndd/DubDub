# BRIEFING — 2026-09-19T14:48:00Z

## Mission
Investigate backend APIs, TTS provider integration, and voice discovery systems for DubDub Stage 3: Voice & Dubbing.

## 🔒 My Identity
- Archetype: explorer
- Roles: Backend & TTS Explorer
- Working directory: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_be
- Original parent: 895741d8-2509-4938-9b8d-b4310925dbdd
- Milestone: Stage 3 Voice & Dubbing Discovery

## 🔒 Key Constraints
- Read-only investigation — do NOT implement changes in codebase
- Produce structured report in report.md and handoff.md in working directory
- Verify all findings with file paths, line numbers, and accurate citations

## Current Parent
- Conversation ID: 895741d8-2509-4938-9b8d-b4310925dbdd
- Updated: 2026-09-19T14:43:49Z

## Investigation State
- **Explored paths**:
  - `webui.py`: lines 1-1095 examined. Found `/api/voices` (681-689), `/api/options` (553-590), `/api/jobs` (717-746).
  - `videotrans/tts/__init__.py`: Catalog v3 examined. Exactly 4 TTS providers retained: ElevenLabs (0), OmniVoice (1), VieNeu-TTS (2, default), Gemini TTS (3).
  - `videotrans/util/help_role.py`: `role_menu` dispatcher and provider-specific voice discovery routines (`get_elevenlabs_role`, `get_f5tts_role`, `get_vieneu_role`, `GEMINITTS_ROLES`).
  - `videotrans/voicejson/elevenlabs.json`: 21 pre-cached voices.
  - `videotrans/configure/_app_params.py`: Configuration persistence for TTS in `params.json`.
  - `videotrans/task/_stage_dubbing.py`: Dubbing execution using `line_roles` dictionary.
  - `frontend/js/state.js`: `WorkflowStore`, `loadVoices()`, `updateBackendConfig('ttsType')`, `updateTargetLanguage()`.
  - `frontend/js/screens/Stage3VoiceDubbing.js`: Currently static/mocked, needs integration with `state.speakerVoiceMap` and `/api/voices`.
  - `frontend/js/components/VideoPlayer.js`: Subtitle rendering and playback synchronization.
  - `tests/test_provider_catalog.py`, `tests/test_webui.py`, `tests/test_vieneutts.py`: Verified test coverage and confirmed removal of legacy TTS (Edge TTS, OpenAI TTS, etc.).
- **Key findings**:
  - `/api/voices` exists in `webui.py` (lines 681-689) taking `ttsType` and `language`.
  - Only 4 providers are supported (Edge TTS was removed in Catalog v3).
  - Schema returned by `/api/voices`: `{"voices": list[str]}`.
  - Backend multi-speaker dubbing in `_stage_dubbing.py` uses `line_roles: dict[str, str]` mapping line numbers to voice roles.
  - Frontend reactive store does not yet have `state.speakerVoiceMap` or per-segment override methods; these must be added.
- **Unexplored areas**: None within the backend & TTS survey scope.

## Key Decisions Made
- Document exact endpoint signatures, request/response models, and concrete implementation recommendations for Stage 3 engineers.

## Artifact Index
- DISPATCH.md — Incoming task dispatch record
- BRIEFING.md — Persistent working memory
- progress.md — Liveness heartbeat
- report.md — Comprehensive backend & TTS survey report
- handoff.md — Standard 5-component handoff report
