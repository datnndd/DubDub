# Stage 2 to Stage 3 LLM Translation Implementation & Handoff Report

## Overview
Implemented the Stage 2 (Review Transcript) to Stage 3 (Voice & Dubbing) LLM translation workflow in DubDub AI Video Dubbing Studio.

When clicking "Proceed to Voice & Dubbing" in Stage 2 (or calling `nextStep()`):
1. **Bypass Check**: If source and target language codes are identical, or if all segments already have non-empty `targetText`, skips translation and advances directly to Stage 3 (`setStep(3)`).
2. **Translation Job Trigger**: Otherwise, activates a full-screen loading modal with semi-transparent backdrop, animated spinner, dynamic progress bar and message, and a cancel button. Disables primary action button to prevent double-submits. Submits translation job via `POST /api/jobs` (`jobType: 'translation'`).
3. **Polling & Progress**: Polls `/api/jobs/{id}` every 500ms, updating the modal's progress percentage and stage message.
4. **1:1 Segment Alignment**: Upon successful completion, matches translated segments 1:1 by `id` or index, updates `seg.targetText`, recalculates `targetCps`/`cps`/`cpsStatus` based on translated text length and segment duration, and preserves all other segment fields (`id`, timestamps, `speakerId`, `speakerName`, `speakerCode`, `speakerColor`, `voiceOverride`, etc.).
5. **Stage 3 Teleprompter & Video Sync**: Advances to Stage 3, populates default voices in `speakerVoiceMap`, and automatically synchronizes teleprompter textareas (`[data-target-input="${seg.id}"]`) and video canvas subtitle overlay (`[data-canvas-subtitle]`).
6. **Cancellation & Failure Resilience**: If cancelled, calls `/api/jobs/{id}/cancel`, stops polling, closes modal, and leaves the user on Stage 2 with data preserved. If failed, dismisses modal, renders dismissible error banner `[data-translation-error]` on Stage 2, and preserves all segment data.

## Files Touched
1. `videotrans/task/taskcfg.py`: Added `segments: Optional[Union[list, tuple]] = None` to `TaskCfgSTS` so `TaskRequest(params).normalize()` accepts `segments`.
2. `videotrans/task/orchestrator.py`: Implemented `run_staged_translation(request, event_sink, cancellation_token)` handling language bypass, cancellation, 1:1 segment mapping, and CPS recalculation.
3. `webui.py`:
   - Updated `JobManager` to accept and execute `translation_runner` for `job_type == "translation"`.
   - Updated `build_task_params` and `create_job_handler` to support `job_type == "translation"` (optional ASR, preserves `segments`).
   - Added `POST /api/translate` direct synchronous translation endpoint.
   - Retained `--reload` and `dev_reload_handler` support.
4. `frontend/js/state.js`:
   - Added `translationPollTimer`, `translationJobId`, `translationModal`, and `translationError` state properties.
   - Added `proceedToVoiceDubbing()`, `pollTranslationJob()`, `cancelTranslation()`, `completeTranslation()`, `handleTranslationError()`, `dismissTranslationError()`, and `syncSpeakerVoices()`.
   - Updated `nextStep()` to route through `proceedToVoiceDubbing()` when on Stage 2.
   - Guarded global `window.dubDubStore` export for headless environments.
5. `frontend/js/components/StatusFooter.js`:
   - In `renderStatusFooter`, when `step === 2`, wired action to `window.dubDubStore.proceedToVoiceDubbing()`, button text "Proceed to Voice & Dubbing", disabled state with spinner when translation modal is active, `data-action="next-step"`, and `data-action-proceed="proceed-to-voice"`.
6. `frontend/js/screens/Stage2ReviewTranscript.js`:
   - Added full-screen loading modal `[data-translation-modal]` with `[data-translation-spinner]`, `[data-translation-progress]`, and `[data-action="cancel-translation"]` / `[data-translation-cancel]`.
   - Added dismissible error banner `[data-translation-error]` with `[data-action="dismiss-translation-error"]`.
7. `frontend/js/components/VideoPlayer.js`:
   - Guarded `state.backend?.outputs` and `state.project?.previewUrl` against undefined access in headless testing.
8. `frontend/js/components/TranslationConfig.js`:
   - Guarded `translationSettingsProvider` matching against undefined provider IDs.
9. `videotrans/configure/signal_hub.py` & `tests/conftest.py`:
   - Ensured `SignalHub` and mock `QObject` safely handle constructor arguments without throwing `TypeError`.
10. `tests/test_stage2_stage3_translation.py`:
    - 12 comprehensive automated tests covering backend orchestrator, WebUI API endpoints, and headless Node.js end-to-end translation workflows.

## Verification Record
- Ran `pytest tests/test_stage2_stage3_translation.py`: 12 passed in 4.35s.
- Ran full affected test suite: `pytest tests/test_stage2_stage3_translation.py tests/test_stage3_voice_dubbing.py tests/test_staged_asr_and_transcript.py tests/test_webui.py tests/test_taskcfg.py`: 130 passed, 0 failed in 7.10s.
