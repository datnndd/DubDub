# Completed plan: pyVideoTrans OCR migration

Date: 2026-09-07 — 2026-09-08

## Outcome

VoiceStudio hard-subtitle extraction now uses a VoiceStudio-owned port of the pyVideoTrans scanner as the default engine. RapidOCR and PaddleOCR remain selectable behind one provider contract. The Dub flow provides an adjustable video ROI, live progress/ETA, automatic Prepare review, and then continues through the existing translation/TTS workflow.

Reference checkout: `C:/Users/ddat2/Downloads/Projects/pyvideotrans`, revision `c5788f7f342d8ee4f480cf034b85855d09b253ba`. The adapted source files are recorded in `backend/engines/hardsub_ocr/ocr/SOURCE.md` and carry their upstream license.

## Implemented

- [x] Port scanner types, text normalization, segment builder, checkpoint and Paddle 2 provider.
- [x] Stream raw ROI frames through one sequential ffmpeg decoder; remove PNG materialization from the default path.
- [x] Support RapidOCR, PaddleOCR 2.x and PaddleOCR 3.x result shapes through one contract.
- [x] Preserve pyVideoTrans change gating, periodic confirmation, confidence retry and cue stabilization defaults.
- [x] Use versioned, atomic checkpoints keyed by video, ROI, provider/model content and scanner parameters; resume active state without decoding from zero.
- [x] Add optional buffered local timing refinement over real frames.
- [x] Carry cancellation and progress counters through sidecar, API, SSE and UI.
- [x] Add model display, draw/move/resize/numeric ROI controls, progress/ETA and Prepare review to Dub.
- [x] Preserve the previous transcript/SRT on cancel, error or an unconfirmed Prepare result.
- [x] Keep the prior implementation for one release behind `OMNIVOICE_OCR_LEGACY=1`.
- [x] Translate OCR UI strings in all 21 locales and update product documentation/changelog.

## Validation

Supplied video: `C:/Users/ddat2/Downloads/BV1gAgS6DEAx-40216888013.mp4`, duration 675.1 s, ROI `(0, 0.8, 1, 1)`, 2 FPS, PaddleOCR 2.10, warm model.

| Run | Time | Cues | Exact text vs reference | Sequence similarity |
|---|---:|---:|---:|---:|
| Unedited pyVideoTrans | 592.657 s | 272 | 272 baseline | 1.0000 |
| VoiceStudio migrated | 230.703 s | 272 | 270 | 0.992647 |
| VoiceStudio legacy | 201.343 s | 271 | 259 | 0.953959 |

The migrated scanner is 2.57x faster than the unedited reference. Its two textual differences were inspected at 314.5 s and 419 s; VoiceStudio reads the visible glyphs correctly in both cases. It has no adjacent overlaps. The legacy path is 29.36 s faster on this host but loses or repeats multiple subtitles, so it remains recovery-only.

The migrated default made 918 provider calls for 1,350 coarse frames, a 32.0% reduction. The proposed 70% experimental target conflicts with pyVideoTrans's accepted every-four-frame confirmation on this dense-subtitle video. The migration preserves the accepted accuracy defaults instead of silently weakening confirmation.

Executable proof:

- Backend OCR unit/integration: 58 focused tests passed with offline Hugging Face settings; the five route/process tests also passed under the project `.venv` (23 tests in their combined files).
- Frontend: 4 Vitest files, 16 tests passed; `bun run typecheck:ci` passed.
- Synthetic coverage includes static subtitles, jitter consensus, repeated text after a gap, adjacent/empty transitions, low-contrast fade, exact timestamps, corrupt checkpoints, resume and cancellation.
- Real PaddleOCR 2 adapter, Windows DLL import order, PaddleOCR 3/RapidOCR result formats, model identity replacement, SRT de-overlap and process-tree cancellation are covered.

Benchmark artifacts are local under `.ocr-benchmark/` and ignored by Git. The reproducible runners are `scripts/benchmark_ocr_migration.py`, `scripts/benchmark_ocr_reference.py`, and `scripts/compare_ocr_benchmarks.py`.

## Residual limits

- Optional refinement costs more calls and time on this video, so it stays off by default.
- Full repository locale parity currently reports unrelated pre-existing missing keys outside the OCR namespace. OCR key parity, JSON validity and placeholder checks pass across all 21 locales.
- Hardware performance varies; user-visible behavior and fallback are cross-platform.

