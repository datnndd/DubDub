# Dispatch for Implementer 1

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
