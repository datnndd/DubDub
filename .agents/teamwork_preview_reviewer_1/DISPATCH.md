# Dispatch for Reviewer 1

<original_task>
This is a single self-contained fix; keep it small and focused. Implement the Stage 2 to Stage 3 LLM Translation flow in DubDub AI Video Dubbing Studio: when clicking "Proceed to Voice Dubbing" in Stage 2, initiate LLM translation of transcript segments, display a full-screen loading modal with progress and cancel support, and upon completion match and insert the translated text into Stage 3 segments for voice dubbing.

Working directory: c:\Users\ddat2\Downloads\Projects\pyvideotrans
Integrity mode: development

## Requirements

### R1. Stage 2 Translation Trigger & Full-Screen Loading Modal
- In Stage 2 (Review Transcript), clicking the primary action button ("Proceed to Voice & Dubbing") initiates translation of the current transcript segments using the selected LLM provider, model, and mode.
- If the source and target languages are identical, or if all segments already have `targetText` populated, bypass translation and proceed directly to Stage 3.
- When translation is required, display a full-screen loading modal overlay with an animated spinner, status and progress feedback, and a "Cancel Translation" action that safely cancels the operation and keeps the user on Stage 2.
- Prevent double-submits while translation is processing.

### R2. Translation Execution & Segment Alignment
- Execute translation via the backend translation pipeline for all segments (`sourceText` -> `targetText`).
- Match each translated result 1:1 back to its corresponding segment by ID and order, preserving `id`, `startSec`, `endSec`, `startTime`, `endTime`, speaker assignments (`speakerId`, `speakerName`), and any manual edits.
- If the backend returns an error or if translation fails, dismiss the loading modal, display an informative error banner/toast, and remain on Stage 2 with all existing transcript edits intact.

### R3. Transition to Stage 3 (Voice & Dubbing)
- Upon successful translation, update `state.segments` in the reactive store (`window.dubDubStore`) with the translated `targetText`.
- Automatically advance to Stage 3 (Voice & Dubbing), where translated dialogue cards in the teleprompter feed and the video preview subtitle bar immediately display the translated text.
- Synchronize speaker voice mapping so that translated segments in Stage 3 inherit their speaker's assigned voice.

## Acceptance Criteria

### Translation Workflow & Loading UI
- [ ] In Stage 2, clicking "Proceed to Voice & Dubbing" when translation is needed renders a full-screen modal overlay with spinner, progress text, and a cancel button.
- [ ] Clicking "Cancel Translation" cancels the job, closes the modal, and leaves the user on Stage 2.
- [ ] If source and target languages are identical, or if all segments already have translated text, clicking "Proceed to Voice & Dubbing" transitions immediately to Stage 3 without re-translating.
- [ ] On translation failure, an error message is displayed and the user remains on Stage 2 without data loss.

### Segment Matching & Store Synchronization
- [ ] Translated text is mapped 1:1 to corresponding segments (`seg.targetText`), preserving segment ID, timing (`startSec`, `endSec`), and speaker metadata.
- [ ] Stage 3 teleprompter cards display the translated text in their editable textareas.
- [ ] Video preview canvas in Stage 3 renders the translated subtitle for the active segment.

### Automated Verification
- [ ] Automated tests in `tests/` cover the translation job submission, segment matching, language bypass check, and Stage 2 -> Stage 3 transition.
- [ ] All tests pass with `pytest`.
</original_task>

<prior_attempt>
> [!WARNING] **Skepticism Disclaimer**
> While all 130 backend orchestrator, WebUI API, and headless Node.js integration tests pass cleanly, I remain moderately skeptical about third-party LLM rate-limit nuances and raw WebSocket/polling latency variations under degraded network conditions in a live browser.

## 1. What I changed
- `videotrans/task/taskcfg.py`: Added `segments: Optional[Union[list, tuple]] = None` to `TaskCfgSTS` so `TaskRequest(params).normalize()` accepts `segments`.
- `videotrans/task/orchestrator.py`: Implemented `run_staged_translation(request, event_sink, cancellation_token)` supporting language bypass (same source/target), task cancellation, 1:1 segment text alignment, and CPS recalculation.
- `webui.py`:
  - Configured `JobManager` to run `_translation_runner` for `jobType == "translation"`.
  - Updated `build_task_params` and `create_job_handler` to support `translation` jobs without requiring ASR engine keys or pre-existing disk media.
  - Added synchronous `POST /api/translate` endpoint.
- `frontend/js/state.js`:
  - Added state fields: `translationPollTimer`, `translationJobId`, `translationModal`, and `translationError`.
  - Implemented `proceedToVoiceDubbing()` with double-submit guard, language bypass check, and pre-populated segments bypass check.
  - Implemented `pollTranslationJob()`, `cancelTranslation()`, `completeTranslation()`, `handleTranslationError()`, `dismissTranslationError()`, and `syncSpeakerVoices()`.
  - Updated `nextStep()` to route through `proceedToVoiceDubbing()` when on Stage 2.
- `frontend/js/components/StatusFooter.js`:
  - Wired Stage 2 primary action button to `window.dubDubStore.proceedToVoiceDubbing()` with text "Proceed to Voice & Dubbing", disabled state while active, and attributes `data-action="next-step"` & `data-action-proceed="proceed-to-voice"`.
- `frontend/js/screens/Stage2ReviewTranscript.js`:
  - Added full-screen loading modal with backdrop, `[data-translation-modal]`, `[data-translation-spinner]`, `[data-translation-progress]`, and `[data-action="cancel-translation"]` / `[data-translation-cancel]`.
  - Added dismissible error banner `[data-translation-error]` with `[data-action="dismiss-translation-error"]`.
- `frontend/js/components/VideoPlayer.js` & `frontend/js/components/TranslationConfig.js`:
  - Guarded against undefined outputs/previewUrl/models in minimal or headless execution contexts.
- `videotrans/configure/signal_hub.py` & `tests/conftest.py`:
  - Fixed `SignalHub.__init__` and mock `QObject` to safely handle parent parameters under mocked PySide6 environments.
- `tests/test_stage2_stage3_translation.py`:
  - Created 12 new automated unit and end-to-end tests covering backend translation, API endpoints, language bypass, pre-populated bypass, cancellation, error handling, and headless Node.js DOM validation.

## 2. Why
The application required a reliable bridge from Stage 2 (Review Transcript) to Stage 3 (Voice & Dubbing). Users needed an automated LLM translation trigger with immediate visual feedback via a loading modal, progress tracking, ability to cancel, bypass when translation is redundant, preservation of all manual cue edits and speaker metadata, and seamless propagation of translated text to the Stage 3 teleprompter and video canvas subtitle overlay.

## 3. Verification Record
- **Deep Verification (ran actual tests):**
  - Ran `pytest tests/test_stage2_stage3_translation.py`: 12 passed.
  - Ran full test suite across touched modules: `pytest tests/test_stage2_stage3_translation.py tests/test_stage3_voice_dubbing.py tests/test_staged_asr_and_transcript.py tests/test_webui.py tests/test_taskcfg.py`: 130 passed, 0 failed in 7.10s.
  - Ran headless Node.js tests verifying live DOM rendering of `data-action-proceed="proceed-to-voice"`, modal attributes `[data-translation-modal]`, spinner, progress percentage, error banner dismiss action, and Stage 3 teleprompter input value propagation.
- **Shallow Verification (manual run only):**
  - CSS animations (Tailwind `animate-spin` and backdrop blur aesthetics) were verified by inspecting template string classes rather than visually rendering on a physical monitor.
- **Unverified aspects:**
  - Real live network calls to OpenAI / DeepLX / Gemini translation APIs (tested using deterministic test doubles and offline mocks).
  - Browser window resize behavior while the modal is open.

## 4. Known Issues
- `Minor Robustness Risk` — If a backend translation provider emits an entirely mismatched count of subtitle items (e.g. LLM hallucinates fewer or extra lines), the 1:1 matcher falls back to positional index matching or retains original text for extra items; non-1:1 subtitle merging from poorly formatted LLM outputs might require manual cue realignment.

## 5. Untested Edge Cases & Next Step
- Reviewers should test edge cases where the LLM translation returns Markdown formatting (e.g. ````json` blocks or conversational preambles) rather than pure SRT text lines when in raw LLM mode.
- Next step: perform manual sanity checks in an active browser session with `python webui.py` to inspect the visual modal layout and real-time spinner fluidness.
</prior_attempt>

<additional_context>
Open Issues Ledger:
- [Open] Real live network calls to OpenAI / DeepLX / Gemini translation APIs (tested using deterministic test doubles and offline mocks) (raised by implementer_1).
- [Open] Browser window resize behavior while the modal is open (raised by implementer_1).
- [Open] Minor Robustness Risk: If a backend translation provider emits an entirely mismatched count of subtitle items (e.g. LLM hallucinates fewer or extra lines), the 1:1 matcher falls back to positional index matching or retains original text for extra items; non-1:1 subtitle merging from poorly formatted LLM outputs might require manual cue realignment (raised by implementer_1).
- [Open] Reviewers should test edge cases where the LLM translation returns Markdown formatting (e.g. ````json` blocks or conversational preambles) rather than pure SRT text lines when in raw LLM mode (raised by implementer_1).
</additional_context>
