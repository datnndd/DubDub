# Execution Plan: Adaptive OCR scan and duplicate suppression

Date: 2026-09-07

## Status

Active

## Outcome

Reduce hard-subtitle OCR wall time by avoiding model inference on frames that
cannot contain a meaningful subtitle change, while preserving subtitle recall,
stable text, and cue boundaries. The 11-minute example must no longer require
multiple passes of OCR over all sampled frames; the measured benchmark will
record the before/after inference count and elapsed time on the same host.

## Context and authority

- Owner request: duplicate detection currently saves no time; optimize the
  extraction/translation path before implementation.
- Current VoiceStudio implementation:
  `backend/engines/hardsub_ocr/main.py::_extract_frames` writes every sampled
  PNG and `_run_ocr` invokes the selected engine for every PNG. The existing
  `group_frames_to_cues` similarity check runs only after inference.
- Existing product contract: `docs/dubbing/hardsub-ocr.md` (selected ROI,
  RapidOCR/PaddleOCR, timestamped cues, existing dubbing stages, local-first).
- Reference implementation: `pyvideotrans/videotrans/ocr/_scanner.py` uses a
  grayscale thumbnail change metric, periodic confirmation, low-confidence
  retries, and `SegmentBuilder`; `_segment.py`, `_text.py`, and
  `_checkpoint.py` define stabilization, normalization, and safe resume/dedup.
- `pyvideotrans/docs/architecture.md` §8.7 and
  `pyvideotrans/docs/decisions/0001-video-ocr-as-subtitle-source.md` describe
  adaptive sampling and local boundary refinement. They are reference material,
  not a new VoiceStudio policy authority.

## Scope

In scope:

- Sidecar sampling/inference scheduling, duplicate-frame cache, cue
  stabilization, local boundary refinement, progress metrics, and checkpoints.
- RapidOCR and PaddleOCR through the existing provider boundary.
- Regression/performance tests and synchronization of OCR documentation and the
  active plan.

Out of scope:

- Changing OCR models, language packs, translation providers, TTS, or the
  existing Prepare/dubbing UX.
- Required network downloads, physical scene splitting, video re-encoding, or
  disabling a working hardware optimization.

## Diagnosis to verify first

1. Capture a warm-model baseline on a fixed fixture: video duration, sample FPS,
   number of sampled frames, OCR calls, elapsed time, and emitted cues.
2. Confirm that the current duplicate/similarity logic is post-inference and
   that each sampled PNG is decoded and sent to the model once.
3. Separate time spent in decode, image materialization, model inference, and
   cue grouping so a faster grouping function is not mistaken for a faster scan.

## Approach

### 1. Stream and gate before OCR

- Replace the all-PNG fan-out with one sequential ffmpeg stream at the coarse
  sampling rate. Keep only the current ROI frame, a small grayscale thumbnail,
  and bounded cue state in memory.
- Compute a normalized thumbnail change metric (the reference uses block-mean
  grayscale thumbnails and mean absolute difference). Do not call OCR when the
  ROI is visually unchanged and the last observation is confident.
- OCR the first frame, frames whose change exceeds the measured threshold,
  frames after an empty-to-nonempty transition, and a periodic confirmation
  frame. Keep periodic confirmation and low-confidence retry intervals
  configurable so static subtitles cannot be lost indefinitely.
- Add an exact thumbnail/hash cache for repeated decoded frames. Cache keys must
  include ROI and model identity; never reuse OCR text across a changed video,
  ROI, language, or model.
- Preserve frame timestamps from the sequential sampler. Do not copy the
  reference's per-frame random ffmpeg seek strategy because launching a decoder
  for every sample would reintroduce avoidable overhead.

### 2. Stabilize text and suppress duplicate cues

- Extract the pure helpers from `pyvideotrans` conceptually: Unicode-aware
  normalization, sequence similarity, containment/token overlap, and a bounded
  `SegmentBuilder` with minimum stable observations and a short empty-gap grace
  period.
- Reuse the current display text from the best/highest-confidence observation;
  use normalized text only as a comparison key.
- Keep identical text separated by a real subtitle gap as two cues. A similar
  OCR flicker may extend the active cue, but a different stable text must close
  the previous cue at the transition.
- Make the “skipped frame” path feed the active state only through time/visual
  continuity; it must never fabricate new text or extend a cue through a proven
  visual subtitle disappearance.

### 3. Refine only around transitions

- Retain cheap grayscale/aHash refinement, but inspect only a bounded window
  around candidate cue starts/ends (100–200 ms step) instead of scanning the
  entire video at a high refinement FPS.
- Decode the actual frame for each refinement timestamp; never reuse the
  transition frame as a proxy. Clamp and de-overlap neighboring cues as today.
- If local refinement fails, return coarse stabilized cues (fail-soft).

### 4. Resume and observability

- Persist a versioned checkpoint at safe boundaries with video fingerprint, ROI,
  language, model, sampler thresholds, last timestamp, completed cues, and
  active candidate state. Resume with a small overlap and similarity dedup, as
  in `pyvideotrans/_checkpoint.py`.
- Extend progress events with `frames_decoded`, `ocr_calls`, `frames_skipped`,
  `cache_hits`, `candidate_transitions`, and stage-specific elapsed/ETA. The
  existing UI can show “scanned” and “OCR calls” without changing the Prepare
  contract.
- Ensure cancellation terminates the stream and removes only the task-owned
  checkpoint/scratch data; a cancelled run must not replace the prior transcript.

## Proposed defaults and authority gate

Use the reference defaults as measured starting points, then tune against the
baseline fixture rather than hard-coding a performance claim:

- coarse interval: 500 ms (existing default);
- thumbnail change threshold: 0.02;
- periodic confirmation: every 4 coarse samples;
- low-confidence retry: confidence below 0.65;
- minimum stable observations: 2;
- empty-gap grace: 400 ms;
- local boundary step: 150 ms.

These are task-local implementation defaults, not a new user-visible policy.
If benchmark evidence shows a recall regression, stop and request the smallest
owner decision on threshold/recall tradeoff before changing the public default.

## Risks and recovery

- A threshold that is too high can miss a subtitle that changes without a large
  pixel delta. Mitigate with periodic confirmation, low-confidence retries,
  transition windows, and a recall fixture with low-contrast/fading text.
- A text-only cache can merge two visually distinct occurrences. Scope cache by
  frame hash plus time/ROI/model and keep gap-aware segment state.
- PaddleOCR and RapidOCR may return different box/result shapes. Keep the
  provider adapter unchanged at the boundary and test both normalized outputs.
- Checkpoint schema changes must invalidate old checkpoints safely; deleting a
  checkpoint only loses resume speed, never source media or the prior
  transcript.
- Recovery: behind the task flag, fall back to the current fixed-sampling
  implementation if the adaptive scanner raises before producing cues. Keep the
  old path until parity tests and the benchmark pass.

## Progress

- [x] Record the current all-frame inference behavior and add a reproducible
  pre-inference gating regression fixture.
- [x] Implement the pre-inference thumbnail change gate and exact-frame cache
  within the existing sequential sampler.
- [x] Preserve/stabilize the existing text similarity and cue grouping behavior.
- [x] Restrict boundary refinement to local transition windows.
- [ ] Add checkpoint/resume and progress counters with cancellation proof.
- [ ] Run recall, duplicate-gap, boundary, cancellation, and performance tests.
- [ ] Update `docs/dubbing/hardsub-ocr.md`, review the diff, and move this plan
  to `docs/plans/completed/` only after validation.

## Validation

- Unit: thumbnail metric, cache key invalidation, text normalization/similarity,
  stable cue grouping, empty-gap separation, local boundary snapping, and
  checkpoint compatibility.
- Integration: fake OCR provider records calls; a fixture with long static
  subtitle intervals must show at least 70% fewer OCR calls than the baseline,
  while retaining all cues within the existing boundary tolerance.
- Sidecar: real RapidOCR fixture with progress/cancellation; PaddleOCR adapter
  smoke test when its optional environment is installed.
- Performance: warm-model before/after elapsed time on the same host and a
  representative 11-minute fixture; report decode time and OCR time separately.
- Repository checks: targeted pytest, frontend Vitest/typecheck/build when UI
  event fields change, `git diff --check`, and the existing offline/local-first
  test environment.

## Implementation update (2026-09-07)

- Adaptive pre-inference thumbnail gate, confidence/periodic retry, signature
  cache, and local transition-window refinement are implemented in the sidecar.
- A real-video smoke attempt was prepared with the supplied 675-second video and
  ROI `(0, 0.8, 1, 1)`, but the installed OCR sidecar did not produce a ready
  event before the bounded run was stopped; no runtime speed claim is recorded.
- Sequential raw-frame streaming and checkpoint/resume remain required before
  this plan can move to `completed/`.

## Measurements (2026-09-07)

- Supplied video duration: 675.10 s. Host ffmpeg decoded the 2 FPS, bottom-20%
  crop to a null sink in 10.27 s; decode alone is not the 37-minute bottleneck.
- Adaptive fixture: 1,351 sampled frames with long static intervals resulted in
  1 OCR call and 1,350 skipped frames. This validates the gate/cache behavior,
  but is not a recognition-quality or end-to-end speed benchmark.

## Result

Pending implementation and measurement.
