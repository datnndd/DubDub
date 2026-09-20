## 2026-09-19T14:51:10Z

<USER_REQUEST>
You are the Test Writer for the DubDub Stage 3: Voice & Dubbing project.
Your assigned working directory is: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_test_writer_1
Project root: c:\Users\ddat2\Downloads\Projects\pyvideotrans

Read the authoritative user request at:
c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\ORIGINAL_REQUEST.md
Specifically header ## 2026-09-19T14:42:14Z and the Stage 3 requirements and acceptance criteria.

Also read:
- Project Plan & Interface Contracts: c:\Users\ddat2\Downloads\Projects\pyvideotrans\PROJECT.md
- Test Infrastructure Specification: c:\Users\ddat2\Downloads\Projects\pyvideotrans\TEST_INFRA.md
- Test Survey Report & Code Samples: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_tests\report.md

Your exclusive write ownership:
`c:\Users\ddat2\Downloads\Projects\pyvideotrans\tests\test_stage3_voice_dubbing.py`
and `c:\Users\ddat2\Downloads\Projects\pyvideotrans\TEST_READY.md`.
Do NOT edit any source code or other files outside your working directory and the test file.

Implement the comprehensive Stage 3 automated test suite in `tests/test_stage3_voice_dubbing.py`:
1. Backend Voice Discovery Endpoint (`GET /api/voices`):
   - Test each of the 4 supported TTS providers: ElevenLabs (0), OmniVoice (1), VieNeu-TTS (2), Gemini TTS (3).
   - Test parameter handling: `ttsType`, `language`, and aliases (`provider`, `target_language`).
   - Test edge cases: invalid ttsType, missing params, error resilience (returns `{"voices": ["No"]}` on exception).
2. Speaker Matrix & Store State Logic:
   - Detecting distinct speakers from `state.segments`.
   - Speaker voice mapping assignment and propagation to non-overridden segments.
   - Per-block voice override (`seg.voiceOverride`).
   - Reset override functionality restoring speaker assigned voice.
   - Updating `targetText` in segment and store.
   - Persistence of `speakerVoiceMap` across workflow transitions.
3. Frontend Component Contracts & DOM Invariants:
   - Format of timestamps (`MM:SS.mmm`).
   - Speaker badge rendering (`speakerName`, `speakerColor`).
   - Inline editable textarea with `data-segment-input="stage3-{seg.id}"`.
   - Selected voice dropdown with `(Default)` indicator for non-overridden blocks.
   - Voice override selection and "Reset to Default" button (`data-action="reset-segment-voice"`).
   - Video seek-and-play click trigger (`data-action="seek-segment"`).
4. Video Player Subtitle Overlay:
   - Presence of `data-canvas-subtitle` and `data-canvas-speaker-badge` in `VideoPlayer.js`.
   - Dynamic canvas subtitle updating in `syncPreviewPlayback` matching active segment's `targetText`.
5. Multi-Speaker Real-World Scenario:
   - End-to-end multi-speaker dubbing scenario asserting full data flow.

After writing `tests/test_stage3_voice_dubbing.py`:
- Run `uv run pytest tests/test_stage3_voice_dubbing.py` (and existing tests like `tests/test_staged_asr_and_transcript.py` / `tests/test_webui.py`).
- Create `c:\Users\ddat2\Downloads\Projects\pyvideotrans\TEST_READY.md` summarizing coverage and test results.
- Write handoff report to `c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_test_writer_1\handoff.md`.
- Notify parent via send_message when complete.
</USER_REQUEST>
