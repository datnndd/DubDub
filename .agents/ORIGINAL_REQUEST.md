# Original User Request

## 2026-09-18T15:13:36Z

This is a single self-contained fix; keep it small and focused. Implement the DubDub AI Video Dubbing Studio multi-stage transcript review workflow: replace the primary footer action with a "Start Dub" preparation flow that performs speech recognition and speaker diarization, automatically advances to Stage 2 upon completion, and presents an interactive transcript review workspace supporting segment playback synchronization, inline editing, playhead/cursor segment splitting, and targeted PaddleOCR subtitle replacement.

Working directory: c:\Users\ddat2\Downloads\Projects\pyvideotrans
Integrity mode: development

## Requirements

### R1. Stage 1 "Start Dub" Button & Asynchronous ASR Execution
- The primary action button in the Stage 1 footer must be labeled **"Start Dub"** (replacing "Choose Source Video" / "Start Processing & Translate"). It remains disabled with an explanatory tooltip until source media is selected and verified.
- Clicking "Start Dub" initiates a staged preparation job that executes audio extraction, speech recognition (ASR) using the selected provider/model, and speaker diarization (if enabled/supported).
- The UI must display an active loading and progress indicator with current stage and percentage feedback during ASR processing.
- Upon successful completion of the ASR stage, the application must automatically transition the user to Stage 2 (Review Transcript) and populate the reactive state store with the recognized transcript segments.

### R2. Stage 2 Transcript Dialog Presentation & Video Synchronization
- Stage 2 must render the recognized transcript as a sequential series of dialog segment cards displaying:
  1. Start timestamp and end timestamp formatted as `MM:SS.mmm`.
  2. Speaker identifier: a clean "Speaker 1" badge when diarization is disabled or single-speaker; distinct colored badges (e.g. Speaker 1, Speaker 2) when diarization detects multiple speakers.
  3. Original recognized dialog text in an editable input/textarea.
- Clicking any dialog segment card must seek the synchronized video player to that segment's `startSec` and immediately begin smooth continuous playback so the user can verify the text against video audio.

### R3. Inline Text Editing
- The recognized text inside each dialog block must be directly editable by the user.
- Any manual text edit must immediately update the reactive store so that downstream stages receive the corrected transcript.

### R4. Intuitive Segment Splitting
- Each dialog segment card must provide an intuitive "Split Segment" action.
- When the video player is paused inside the segment's duration (`startSec < currentTime < endSec`), triggering the split action must divide the segment at the current playhead timestamp.
- If the text editor cursor is active, the text must split at the cursor position; otherwise, it splits cleanly at the nearest word boundary.
- The two resulting segments must have contiguous, non-overlapping timestamps (`[start, split]` and `[split, end]`), preserve speaker assignment, and remain independently editable and seekable.

### R5. Targeted PaddleOCR Subtitle Replacement
- Stage 2 must provide a "Replace with OCR" action on each dialog segment card.
- Triggering "Replace with OCR" activates an interactive ROI crop box overlay on the video player for the user to adjust/confirm the subtitle region.
- Once confirmed, the backend must execute the existing PaddleOCR pipeline exclusively for the video frames within the selected segment's time range `[startSec, endSec]`.
- The extracted OCR subtitle text must automatically replace or update the selected dialog segment's text in the store and UI.

## Acceptance Criteria

### UI & Workflow Transitions
- [ ] On Stage 1, the primary footer button is labeled "Start Dub", is disabled before video ingest, and becomes enabled once a video is verified.
- [ ] Clicking "Start Dub" starts the job, renders progress/loading state, and automatically navigates to Stage 2 on completion without requiring manual step clicks.
- [ ] If ASR fails, an informative error message is displayed and the user remains on Stage 1.

### Video Synchronization & Playback
- [ ] Clicking any dialog card seeks the `<video>` element to `startSec` and starts playback.
- [ ] The playhead timecode in the HUD and waveform scrubber updates synchronously with video playback.

### Segment Editing & Splitting
- [ ] Modifying text in any dialog segment updates `state.segments` in the store and persists across stage navigation.
- [ ] Splitting a segment at timestamp `T` creates two valid segments where segment 1 has `[startSec, T]` and segment 2 has `[T, endSec]`.
- [ ] Splitting with an active cursor divides the text at the cursor; splitting without active cursor divides text at the nearest word boundary.

### PaddleOCR Integration
- [ ] Clicking "Replace with OCR" displays an interactive ROI selection box on the video canvas.
- [ ] Confirming the ROI sends a request to the backend with `mediaId`, `[startSec, endSec]`, and `roi`.
- [ ] The backend runs PaddleOCR on the extracted frames for that duration and returns the recognized text.
- [ ] The selected segment's `sourceText` is updated with the returned OCR text and reflected immediately in the UI.

### Automated Verification
- [ ] Automated tests in `tests/` cover the staged ASR job runner, segment splitting logic, and OCR frame range extraction endpoint.
- [ ] Python tests pass with `pytest`.

## 2026-09-19T14:42:14Z

Use a full multi-agent team. Implement **Stage 3: Voice & Dubbing** in DubDub AI Video Dubbing Studio: provide a dedicated TTS provider and voice selection console, support speaker-to-voice mapping with per-block voice overrides, render translated dialog blocks with synchronized video seek and playback, and display live translated subtitles on the video preview.

Working directory: c:\Users\ddat2\Downloads\Projects\pyvideotrans
Integrity mode: development

## Requirements

### R1. Dedicated TTS Provider & Voice Discovery Console
- Provide a dedicated voice configuration console in the upper-right deck of Stage 3 (`Stage3VoiceDubbing.js`).
- The console must allow selecting any supported TTS provider (ElevenLabs, OmniVoice, VieNeu-TTS, Gemini TTS) from the backend configuration.
- Changing the TTS provider must dynamically fetch and update the available voices for that provider and the current target language via `/api/voices`.
- The current selected voice and provider must be stored in the reactive store (`window.dubDubStore`) and kept synchronized with Stage 1 and downstream stages.

### R2. Global Speaker-to-Voice Mapping Matrix
- In the Voice Casting console, dynamically detect all distinct speakers from `state.segments` (e.g. Speaker 1, Speaker 2).
- Render an assignment control for each detected speaker displaying their name/badge and a dropdown to assign a specific TTS voice from the currently loaded provider voices (e.g., Speaker 1 → Voice A, Speaker 2 → Voice B).
- Updating a speaker's assigned voice must immediately propagate to all translated dialog blocks belonging to that speaker across the teleprompter feed.
- Maintain the mapping in `window.dubDubStore` (e.g. `state.speakerVoiceMap`) so it persists across stage navigation.

### R3. Translated Dialog Blocks with Per-Block Voice Overrides
- Render each translated dialog block in the Stage 3 teleprompter feed displaying:
  1. Start timestamp and end timestamp formatted as `MM:SS.mmm`.
  2. Speaker identifier / badge matching the stage 2 styling.
  3. Translated subtitle text in an inline editable textarea (`seg.targetText`) that updates the reactive store on edit.
  4. Selected TTS voice dropdown displaying the speaker's assigned default (e.g. `Voice A (Default)`).
- Allow users to override the voice for an individual dialog block by selecting a different voice in its dropdown, visually indicating the override.
- Provide a "Reset to Default" button on overridden blocks to revert back to the speaker's global assigned voice.
- When a speaker's global voice is changed in the upper console, all blocks for that speaker update automatically except those with an explicit per-block override.

### R4. Video Preview Subtitle Overlay & Synchronized Playback
- Display the translated subtitle text for the currently active/playing segment directly on the video canvas bottom subtitle bar.
- Clicking any translated dialog block must seek the synchronized video player to that segment's `startSec` and immediately begin smooth continuous playback.
- The video playhead timecode in the HUD and scrubber must synchronize with playback, and the on-screen subtitle must dynamically match the segment at `currentTime`.

## Acceptance Criteria

### TTS Provider & Voice Loading
- [ ] In Stage 3, changing the TTS provider dropdown triggers `/api/voices` and populates the available voices list.
- [ ] The available voices update whenever the target language or TTS provider changes.

### Speaker-to-Voice Mapping
- [ ] Distinct speakers from `state.segments` appear in the Voice Casting console with their own voice assignment dropdown.
- [ ] Selecting a voice for Speaker X updates all dialog blocks associated with Speaker X that do not have an individual override.
- [ ] Speaker-to-voice mapping persists in `state.speakerVoiceMap` when switching between workflow stages.

### Dialog Block Representation & Overrides
- [ ] Each dialog block displays formatted start/end times (`MM:SS.mmm`), speaker badge, editable translated text (`targetText`), and a voice selector.
- [ ] Editing `targetText` in any dialog block immediately updates `state.segments` and the video preview subtitle.
- [ ] Selecting a different voice on an individual block sets `seg.voiceOverride` without altering other blocks of the same speaker.
- [ ] Overridden blocks show a reset button; clicking it clears `seg.voiceOverride` and restores the speaker's global voice.

### Video Synchronization
- [ ] Clicking any dialog block in Stage 3 seeks the video player to `startSec` and begins continuous playback.
- [ ] The video canvas subtitle bar renders the active segment's `targetText` with the speaker badge during playback.

### Automated Verification
- [ ] Automated tests in `tests/test_stage3_voice_dubbing.py` (or added to `tests/test_webui.py`) verify:
  1. Speaker-to-voice mapping propagation and override logic in state.
  2. Voice fetching and backend voice role options endpoints.
  3. Frontend component rendering of Stage 3 controls and teleprompter blocks.
- [ ] All automated tests pass with `uv run pytest`.

## 2026-09-20T03:04:42Z

Use a full multi-agent team. Redesign **Stage 4: Edit Video** in DubDub AI Video Dubbing Studio as an intuitive, lightweight video editing studio inspired by CapCut. The studio allows users to review the final dubbed video and make simple adjustments before exporting without turning the application into a complex video editor.

Working directory: c:\Users\ddat2\Downloads\Projects\pyvideotrans
Integrity mode: development

## Requirements

### R1. Studio Layout & Synchronized Video Preview
- Provide an intuitive 3-area layout: Widescreen Video Preview area (top-left), Contextual Settings Panel / Inspector (top-right), and a Multi-Track Timeline (bottom).
- The video preview must display translated subtitles rendered directly over the canvas without teleprompter card wrapping in a clean readable default style (white text, black outline, subtle shadow, centered near bottom).
- The player must support real-time preview of all active audio sources simultaneously (original audio, dubbed TTS, and background music) in sync with the playhead and volume settings.

### R2. Multi-Track Timeline Editing Area
- Render a track-based timeline with visual lanes for Video, Subtitles, Dubbed TTS Audio, and Background Music (BGM).
- The timeline serves as a review and navigation workspace: clicking anywhere on the timeline or time ruler seeks the playhead, and clicking a subtitle cue seeks to that segment, highlights it, and activates its editor in the settings panel.
- Include an interactive playhead timecode indicator and scrubber needle spanning all tracks that updates in real time during playback.

### R3. Audio Source Separation & Background Music Control
- Clearly separate audio source controls for Original Video Audio, Dubbed TTS Audio, and Background Music.
- Provide independent volume sliders (0–150%) and mute/unmute toggles for each source.
- Support uploading, replacing, and removing background music (`audio/*`), playing it in sync with video play/pause/seek during client preview.
- Clicking "Render dubbed video" sends the configured mix levels (`originalAudioVolume`, `backgroundAudioVolume`, `volume`) and background audio ID to the backend render task pipeline.

### R4. Subtitle Typography & Font Size Adjustment
- Allow adjusting subtitle font size dynamically via a slider and number input, updating the preview canvas immediately.
- Maintain simple and readable defaults: white text (`#FFFFFF`), black outline (2px), subtle shadow, centered near the bottom of the video.
- Support inline editing of the active subtitle cue's text and start/end timecodes in the inspector, immediately updating `state.segments` and export SRT.

### R5. Video Thumbnail Management
- Allow users to upload or replace the video thumbnail (PNG, JPG, WEBP) with an instant aspect-video preview card in the inspector.
- Support removing/resetting the thumbnail to the default first video frame.

## Acceptance Criteria

### Studio Layout & Video Preview
- [ ] Video preview renders the video with a synchronized timecode HUD and transport controls.
- [ ] Subtitles display directly over the video canvas without card wrapping, centered near bottom with white text, black outline, and shadow.
- [ ] Seeking or playing the video synchronizes both video audio and background music simultaneously.

### Multi-Track Timeline
- [ ] Timeline renders visual lanes for Video, Subtitles (proportional cue blocks), Dubbed TTS, and Background Music.
- [ ] Clicking any subtitle block seeks the playhead to `startSec` and activates its editor in the inspector.
- [ ] Playhead needle moves smoothly across all tracks during video playback.

### Audio Separation & BGM
- [ ] Independent volume sliders for Original Video Audio, Dubbed TTS, and Background Music update store state and real-time audio playback.
- [ ] Background music can be added, replaced, muted, or removed, and plays in sync with the video playhead.
- [ ] Export request payload contains separate volume levels for original audio, dubbed audio, and background music.

### Subtitle Styling & Editing
- [ ] Subtitle font size slider resizes on-screen subtitles in real-time.
- [ ] Selected subtitle text can be edited and updates `state.segments` and export SRT.

### Thumbnail Management
- [ ] Uploading an image file sets `state.editVideo.thumbnail` and shows an aspect-video preview.
- [ ] Thumbnail removal restores default state.

### Automated Verification
- [ ] Automated tests in `tests/test_stage4_edit_video.py` verify timeline tracks, audio mix sliders, subtitle font sizing, and thumbnail controls.
- [ ] All tests pass with `uv run pytest`.

## 2026-09-22T04:10:53Z

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

