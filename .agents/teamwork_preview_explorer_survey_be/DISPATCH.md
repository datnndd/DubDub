## 2026-09-19T14:43:49Z

You are the Backend & TTS Explorer for the DubDub Stage 3: Voice & Dubbing project.
Your assigned working directory is: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_be
Project root: c:\Users\ddat2\Downloads\Projects\pyvideotrans

Read the authoritative user request at:
c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\ORIGINAL_REQUEST.md
Specifically header ## 2026-09-19T14:42:14Z and the Stage 3 requirements R1-R4.

Investigate the backend APIs and TTS provider system:
1. Search for `/api/voices` or voice-related endpoints in the webui server (`pyvideotrans/webui/` or `app.py` / routers).
2. How are TTS providers (ElevenLabs, OmniVoice, VieNeu-TTS, Gemini TTS, Edge TTS, etc.) supported, configured, and exposed to the webui?
3. What does `/api/voices` expect for query parameters (e.g., `provider`, `language` / `target_language`) and what schema/data does it return?
4. If `/api/voices` does not yet exist or is incomplete for the required providers, what backend functions / registries in `pyvideotrans` list available voices for these providers?
5. How does the backend communicate with the frontend reactive store or configuration?

Write a comprehensive report to `c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_be\report.md`.
Include concrete file paths, line numbers, endpoint signatures, request/response models, and recommended implementation steps.
When complete, notify parent via send_message with the report path and summary.
