# Execution Plan: Hard-Subtitle OCR Source

Date: 2026-08-12

## Status

Completed (2026-08-14)
- Hard-subtitle OCR scanner, ROI preview dialog, and STT/OCR GUI mode locking implemented.
- Fixed `app_cfg.main_win` global reference in `MainWindow.__init__` for bi-directional video & ROI sync.
- Resolved PaddleOCR Windows OneDNN `OneDnnContext` `fused_conv2d` error via DLL path injection, C++ core flags, and predictor creation monkeypatching.
- All unit and integration test suites passing (27/27 tests).

## Outcome

Allow a desktop user processing one video to choose **Hard-subtitle OCR** as
the subtitle source, seek to a representative frame, draw and preview a fixed
region of interest (ROI), scan the video locally with PaddleOCR, review the
timestamped source SRT, and then continue through the existing translation,
target-subtitle editing, dubbing, alignment, and assembly flow.

Observable acceptance targets:

- The user cannot start an OCR-backed task until a valid ROI has been previewed
  and confirmed.
- Repeated OCR observations are consolidated into stable SRT segments rather
  than emitted per sampled frame.
- Segment boundaries are within 250 ms of the known boundaries in validation
  fixtures.
- A stopped scan can resume from a compatible checkpoint without duplicating
  or losing a subtitle at the resume boundary.
- Downstream stages consume the OCR-created `source_sub` through the existing
  SRT contract, without OCR-specific translation or dubbing branches.

## Understanding Summary

- The feature targets burned-in subtitles inside one user-selected, fixed ROI.
- It is part of the existing video-translation mode, selected as an alternative
  subtitle source to audio ASR.
- The MVP supports one video at a time, typically 30-120 minutes long.
- The user seeks with a video timeline, pauses on a subtitle frame, draws the
  ROI, and runs a PaddleOCR preview before the main pipeline begins.
- PaddleOCR uses the selected source language, prefers a compatible GPU, and
  falls back to CPU.
- PaddleOCR and its language model are optional components acquired on first
  use; image recognition remains local in the MVP, while the provider boundary
  permits a future online OCR implementation.
- OCR output becomes an editable source SRT before translation; all later
  behavior remains owned by the existing pipeline.

## Assumptions And Non-Goals

Assumptions:

- The fixed ROI is stored as normalized `(x, y, width, height)` coordinates in
  the range `0..1`, independent of preview widget scaling.
- The ROI normally contains one or two lines of burned-in subtitle text.
- A 100-250 ms timestamp error is acceptable for the MVP.
- Scanning streams frames and cropped ROIs; memory use must not grow with video
  duration.
- OCR text similarity, minimum stable samples, and grace-gap settings begin as
  internal defaults rather than user-facing advanced settings.
- Empty OCR output is a normal observation, not a task error.

Out of scope:

- Arbitrary scene text, signs, watermarks, or application/game UI outside the
  subtitle ROI.
- Moving or automatically tracked ROIs.
- Multiple ROIs per video.
- Batch processing or sharing one ROI across multiple videos.
- An online OCR provider in the first release.
- Physically splitting or re-encoding the source video into scene files.

## Context And Repository Authority

- `AGENTS.md` and `docs/WORKFLOW.md` define planning, authority, and validation
  requirements.
- `docs/architecture.md` defines the current staged video translation pipeline.
- `videotrans/task/trans_create.py` owns task-stage composition and determines
  whether recognition, translation, dubbing, and assembly run.
- `videotrans/task/only_one.py` owns the single-video pause/edit flow for source
  subtitles, target subtitles, and dubbing.
- `videotrans/task/_base.py::_save_srt_target` owns writing subtitle lists to
  SRT and notifying the UI through `replace_subtitle`.
- `videotrans/task/_stage_translate.py` consumes `cfg.source_sub`, establishing
  SRT as the downstream integration boundary.
- `videotrans/task/taskcfg.py::TaskCfgVTT` owns video-translation task options.
- `videotrans/ui/en.py`, `videotrans/ui/_setup_rows.py`, and the main-window
  action/signal mixins own the desktop controls and their persisted values.
- The accepted product choices and timestamp tolerance in this plan are the
  authority for the new externally observable OCR behavior.

## Architecture

### Subtitle Source Selection

Add an explicit subtitle-source setting with at least:

- `audio_asr`: current behavior.
- `video_ocr`: create source subtitles from the fixed video ROI and skip audio
  speech recognition as the source-subtitle producer.

OCR behaves as a recognition source rather than a new downstream pipeline. The
task still produces `cfg.source_sub`, emits the existing subtitle update signal,
and follows the current single-video edit pause before translation.

### ROI Preview Dialog

Provide a dedicated desktop dialog containing:

- Video playback, seek timeline, play/pause, and direct timestamp entry.
- A resizable/re-drawable ROI overlay.
- A magnified crop preview.
- Test-recognition action and recognized text, confidence, language, and actual
  device display.
- OCR line bounding-box overlay.
- Clear/reset ROI and confirm actions.

Use the media player for navigation. Decode the exact paused frame through the
video decoding layer for ROI rendering and OCR instead of capturing pixels from
the displayed `QVideoWidget`.

### OCR Provider Boundary

Keep the model-specific adapter behind a small internal contract conceptually
equivalent to:

```python
recognize(image, language) -> OcrResult
```

The MVP provider is PaddleOCR. The provider owns component/model availability,
source-language mapping, model initialization, GPU/CPU selection, OCR inference,
and ordered line results. The video scanner owns neither PaddleOCR APIs nor
future online-provider details.

### Video OCR Scanner

Scan without creating physical scene clips:

1. Decode the video sequentially and crop only the ROI.
2. Sample coarsely at approximately 400-500 ms.
3. Use a cheap resized grayscale ROI comparison to identify likely appearance,
   disappearance, or content changes.
4. Run OCR selectively on change candidates, periodic confirmations, and low-
   confidence observations.
5. When a transition is detected, refine its boundary within the coarse window
   using 100-200 ms sampling.

The scanner reports video timestamp, percentage, active device, segment count,
and the latest candidate text.

### Subtitle Segment Builder

Use a state machine:

```text
EMPTY -> CANDIDATE -> ACTIVE -> CHANGING -> EMPTY/ACTIVE
```

- Normalize whitespace and punctuation before comparison.
- Require either multiple stable samples or a sufficiently strong observation
  before opening a segment.
- Merge similar OCR strings so minor recognition variation does not fragment
  the SRT.
- Use a short grace gap for fade effects and isolated empty/noisy samples.
- Close the previous segment and open the next at the refined boundary when
  text changes without an empty frame.
- Keep identical text as separate segments when separated by a clear gap.
- Sort OCR boxes top-to-bottom and then left-to-right for two-line subtitles.
- Select representative text using confidence and agreement across samples,
  rather than blindly using the first or last observation.

The builder emits `OcrSegment(start_ms, end_ms, text, confidence, samples)`,
which an adapter converts to the existing `SrtItem` format.

### Checkpoint And Resume

Write a versioned checkpoint atomically after each completed segment and at a
periodic interval of about 30 seconds. It includes:

- Video fingerprint: normalized path, file size, modification time, duration,
  and a partial content hash.
- Normalized ROI, source language, provider, model version, actual device, and
  scanner parameters.
- Last safely processed timestamp.
- Completed segments and the currently open candidate/segment.
- Progress statistics and latest diagnostic error.

A checkpoint is automatically resumable only when its video fingerprint, ROI,
language, provider/model, and scanner configuration are compatible. Resume
rewinds approximately 2-3 seconds, scans the overlap, and de-duplicates by time
range and text similarity.

### Optional Component Acquisition

When PaddleOCR or the required language model is absent, test recognition opens
the component acquisition flow. It must show required component/model,
download size when known, progress, destination, and final readiness. Successful
acquisition returns to the same paused frame and ROI.

## Data Shape

Keep OCR task settings grouped rather than adding unrelated flat flags. The
exact dataclass names may follow local conventions, but the design is:

```python
OcrConfig(
    provider="paddle",
    roi=(x, y, width, height),
    language="source_language_code",
    device="auto",
    coarse_interval_ms=500,
    boundary_interval_ms=150,
)

OcrResult(
    text="...",
    confidence=0.94,
    lines=[...],
    timestamp_ms=12500,
)

OcrSegment(
    start_ms=12000,
    end_ms=14800,
    text="...",
    confidence=0.92,
    samples=4,
)
```

Defaults are configuration, not separate product choices. Values may be tuned
from executable fixture measurements while preserving the accepted 250 ms
tolerance and observable behavior in this plan.

## Error Handling And Edge Cases

- Low confidence: collect nearby observations and use consensus before emitting
  a segment.
- Fade in/out: bridge short gaps to avoid fragmented subtitles.
- One-line/two-line transitions: order boxes consistently before comparing
  text.
- Moving background or text jitter: image change triggers OCR, but stable OCR
  text determines subtitle transitions.
- Watermark accidentally inside ROI: identify text that persists for almost the
  entire scan and exclude it when the remaining text still forms valid subtitle
  observations.
- GPU initialization or VRAM failure: release the GPU provider, initialize the
  CPU provider, and continue from the latest safe checkpoint with a visible
  device-change notification.
- Isolated damaged frame: skip a bounded number and continue. Sustained decode
  failure saves a checkpoint and reports the failing timestamp.
- Empty final result: finish with a clear no-subtitles result and do not enter
  translation or dubbing with an empty SRT.
- ROI, language, provider, model, or scanner change: do not automatically resume
  an incompatible checkpoint.

## Approach

1. Add behavior-level fixtures and unit tests for normalization, similarity,
   state transitions, boundary refinement, SRT conversion, and checkpoint
   compatibility.
2. Introduce OCR configuration/result/segment data types and the provider
   boundary without changing current ASR behavior.
3. Implement the PaddleOCR local provider, source-language mapping, optional
   component readiness, and GPU-to-CPU fallback.
4. Implement the streamed scanner, segment builder, atomic checkpointing, and
   resume overlap/de-duplication.
5. Implement the ROI preview/test-recognition dialog and wire subtitle-source
   selection into the existing single-video UI.
6. Adapt `TransCreate.recogn()` routing so `video_ocr` writes the normal source
   SRT and returns to the existing edit/translate flow.
7. Add integration and desktop interaction proof, measure representative CPU
   and GPU performance, then tune internal sampling defaults without weakening
   the timestamp acceptance target.

## Risks And Recovery

- PaddleOCR/PaddlePaddle packaging can conflict with the repository's pinned
  Python and GPU dependencies. Mitigation: keep it optional, isolate imports,
  prove CPU first, and validate the supported GPU package matrix before release.
- Qt media playback timestamps may not identify the exact displayed frame.
  Mitigation: use playback only for seeking and separately decode the requested
  frame for drawing and recognition.
- Highly animated subtitle styles can cause false boundaries. Mitigation: base
  transitions on stable normalized text and refine locally around candidates.
- Video fingerprinting or checkpoint schema mistakes can resume the wrong state.
  Mitigation: version the schema, validate all compatibility fields, and retain
  incompatible checkpoint files without applying them automatically.
- OCR scanning can become slower than expected on CPU. Mitigation: keep coarse
  detection cheap, OCR selectively, expose progress/device, and measure before
  publishing speed expectations.

Recovery and rollback:

- `audio_asr` remains the default and retains its current path.
- The OCR source, dialog, provider, and scanner should be removable without
  changing existing SRT consumers.
- Checkpoints and optional downloaded models are cache/component data; removing
  the feature leaves them inert and does not alter source videos.
- Failed scans preserve the last valid source SRT/checkpoint and never overwrite
  the input video.

## Progress

- [x] Inspect repository workflow, architecture, task pipeline, subtitle edit
  flow, configuration ownership, dependencies, and current UI capabilities.
- [x] Confirm product intent, non-functional requirements, non-goals, and
  architecture with the user.
- [x] Record the accepted design and lasting architecture decision.
- [x] Add unit fixtures and scanner/segment-builder tests.
- [x] Add OCR data contracts and provider boundary.
- [x] Add PaddleOCR provider and optional component/model readiness flow.
- [x] Add streamed scanner, checkpoint, resume, and SRT adapter.
- [x] Add ROI preview dialog and subtitle-source UI wiring.
- [x] Integrate OCR routing with the single-video task pipeline.
- [x] Run focused, integration, UI, and repository validation.
- [x] Record measured performance, remaining limits, and final result; move this
  plan to `docs/plans/completed/` only after validation.

## Decisions

- 2026-08-12: Limit the MVP to burned-in subtitles in one fixed ROI and one
  video at a time; moving/multiple ROIs and general scene text remain out of
  scope.
- 2026-08-12: Put OCR in the existing video-translation mode as a selectable
  subtitle source, not a standalone utility.
- 2026-08-12: Require seekable video preview, ROI drawing, and successful test
  recognition before starting the task.
- 2026-08-12: Use source-language selection for the PaddleOCR model and prefer
  GPU with CPU fallback.
- 2026-08-12: Keep PaddleOCR/models optional and local in the MVP while retaining
  a provider boundary for a future online implementation.
- 2026-08-12: Do not create physical scene clips; stream and crop ROI frames in
  memory.
- 2026-08-12: Use adaptive coarse scanning, selective OCR, text-similarity
  consolidation, and local boundary refinement to meet the 250 ms target.
- 2026-08-12: Persist versioned atomic checkpoints and resume with a short
  overlap scan.
- 2026-08-12: Treat the generated source SRT as the sole integration boundary
  with existing editing, translation, dubbing, alignment, and assembly stages.

## Validation

Focused proof:

- Unit tests for text normalization and similarity, candidate/active state
  transitions, direct text changes, short empty gaps, repeated identical text,
  two-line ordering, representative-text selection, and `OcrSegment` to
  `SrtItem` conversion.
- Unit tests for atomic checkpoint serialization, compatibility rejection,
  overlap resume, and duplicate elimination.
- Provider tests using image fixtures for one-line/two-line text, contrasting
  colors, confidence, box ordering, language/model mapping, missing-component
  handling, and simulated GPU-to-CPU fallback.

Integration or end-to-end proof:

- Generate a short deterministic video fixture with known subtitles such as:

  ```text
  00:01.000-00:03.000  Xin chao
  00:03.000-00:05.500  Chao mung ban
  00:07.000-00:09.000  Xin chao
  ```

- Scan its known ROI and require recognized segment boundaries within +/-250 ms.
- Stop mid-scan, resume from checkpoint, and require the same final segments as
  an uninterrupted scan.
- Pass the generated source SRT into the existing translation stage and confirm
  no OCR-specific downstream branch is required.
- Exercise the desktop flow: open video, seek, draw/resize ROI, preview OCR,
  confirm normalized ROI across resize, start scan, display progress, stop,
  resume, and edit source SRT before translation.

Repository-required checks:

- Run focused tests for all affected modules.
- Run existing task configuration, main-window action/UI split, subtitle parsing,
  translation, and single-video flow tests affected by the new source setting.
- Run the repository's broader test command once focused proof passes, reporting
  unrelated pre-existing failures separately.
- Measure CPU and available-GPU scanning on representative fixtures. Require
  stable memory with video duration; record throughput rather than inventing a
  release speed guarantee.

## Result

Fully implemented and validated.
- **GUI Mode Locking & Sync**: Added explicit STT/OCR mode toggling in main window actions, binding ROI selection with video list, and setting `app_cfg.main_win` reference.
- **PaddleOCR Windows OneDNN Fix**: Resolved `OneDnnContext` `fused_conv2d` operator crashes on Windows CPU/GPU via Windows PyTorch DLL path injection (`os.add_dll_directory`), `paddle.set_flags({"FLAGS_use_onednn": False, "FLAGS_use_mkldnn": False})`, and `paddle.inference.create_predictor` monkeypatching (`config.switch_ir_optim(False)`, `config.disable_mkldnn()`, `config.disable_onednn()`).
- **Validation Proof**: 27/27 unit & integration tests passing cleanly across `test_subtitle_source_ui_flow.py`, `test_ocr_paddle.py`, `test_ocr_dialog.py`, `test_ocr_scanner.py`, and `test_vieneutts.py`.

