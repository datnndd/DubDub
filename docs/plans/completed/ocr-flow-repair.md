# Execution Plan: OCR flow repair

Date: 2026-09-06

## Status

Completed (2026-09-07)

## Outcome

Extract subtitles through the existing Dub workflow, preserve the selected
region, publish progress and usable segments/SRT, and recover from failures.

## Context

- Authority: `CLAUDE.md` fix quality and local-first rules;
  `docs/dubbing/hardsub-ocr.md` extraction, crop, and transcript behavior.
- Owners: OCR sidecar/service, `dub_core.py`, `useDubWorkflow.js`.
- Nine files already have local OCR edits. Preserve this baseline.

## Scope

Trace upload/preparation, crop, extraction, cue/SRT application, and UI completion.
No release, dependency upgrades, model downloads, or unrelated cleanup.

## Approach

1. Read current implementation and run existing focused tests offline.
2. Reproduce boundary failures with behavioral regression tests.
3. Apply minimal fixes, validate real ffmpeg/installed OCR where available.
4. Synchronize OCR docs and record checks and limitations.

## Risks And Recovery

- Existing uncommitted edits: edit only diagnosed paths; never reset files.
- Keep tests isolated from user projects and use an empty Hugging Face cache.
- Real OCR depends on the installed model; report any unavailable proof.

## Progress

- [x] Read project rules and map the existing OCR flow.
- [x] Establish baseline and failing regression cases.
- [x] Fix demonstrated failures.
- [x] Run focused/integration checks and synchronize documentation.

## Decisions

- 2026-09-06: Use bug-hunter skill and repository-native pytest/Vitest.
- 2026-09-06: Preserve current defaults; repair existing contracts without
  introducing new product policy.

## Validation

- Baseline: existing OCR tests passed (15); new tests demonstrated crop-top,
  subtitle ordinal, empty clamped result, SRT timing, cancellation, immediate
  response, wrong active task, and editor recovery failures before fixes.
- Backend: `python -m pytest tests/test_hardsub_ocr.py
  tests/test_hardsub_flow_regressions.py tests/test_srt_parser.py
  tests/test_no_hardcoded_cjk.py tests/test_app_version.py -q`: 42 passed.
  All Python runs used `HF_HUB_OFFLINE=1` and a fresh empty `HF_HUB_CACHE`.
- Frontend: `bun run test src/test/dubHardsubWorkflow.test.jsx
  src/test/dubAsrInstallRecovery.test.jsx src/test/dubVoiceMatchRequest.test.jsx`:
  12 passed. Includes real hook/store behavior for completion, failure, and abort.
- `bun run build` and `bun run typecheck:ci` passed. The final abort-listener
  adjustment was subsequently verified through the targeted Vitest tests.
- Targeted oxlint: no errors; existing file-size and unrelated hook dependency
  warnings remain. Removed unnecessary dependencies in the OCR callback.
- Real installed RapidOCR/ONNX sidecar + generated 640x360 video: top crop
  `{left:0, top:0, right:1, bottom:0.3}` recognized `HELLO WORLD`, emitted
  three progress events, and produced the expected 0–2s SRT. Repeated after
  changing scratch-directory ownership; no model installation was needed.
- Cancellation fixture uses real Python parent/child processes; both stop.
- Chromium layout reproduction: portrait 360x640 in a 720px container at
  800px viewport height had a 720x440 overlay before correction; afterwards
  247.5x440 matches the visible image. Used Node with installed Chromium 1234.
- OCR labels exist in all 21 locales, including matching count placeholders.
  Existing locale validation excluding the two known failing rule groups:
  147 passed, 41 deselected (the full run and baseline failures are above).
- The complete requested policy-check set exposed 22 pre-existing failures:
  19 locale missing-key ratchets, placeholder-only `engines.languagesMany`
  values in en/vi, and existing changelog formatting/reference violations.
  Compared locale data against HEAD: e.g. ar missing keys improved 537 → 523,
  vi remains 495, with no newly missing keys. Changelog was unchanged.
- `git diff --check` passed.

## Result

Fixed the demonstrated extraction and UI failures while preserving the nine
pre-existing local edits. Cancellation stops the OCR process tree, cleans its
parent-owned frame directory, and prevents transcript replacement. The top-edge
and portrait crops now agree with the selected video region. Soft-sub results
complete synchronously; SRT timing matches the clamped transcript. OCR controls
use i18n and all OCR keys are translated in all 21 locales. Updated the OCR
guide to describe current region and optional-refinement behavior accurately.

Limits: real execution was on Windows with a generated English fixture, not
the user's unavailable problem video or a recognition-quality benchmark.
macOS/Linux execution and full application end-to-end interaction were not
performed. Repository-wide locale/changelog failures remain outside this OCR
repair. No commit, PR, merge, release, version bump, or dependency change.
Release-note references must be supplied when this local work gets a real PR;
none were fabricated. Local tool friction: bare pytest hit a stale Windows
temporary-directory link (used isolated basetemp); Bun/Playwright launch hung
(Node with the installed browser worked). No Harness guidance was changed.

Scratch cleanup: automatic approval review rejected the workspace-validated
recursive removal of the eight `.pytest-ocr-*` test directories with
`blocked by policy`. Those generated directories remain; no cleanup bypass
was attempted. They contain only this run's isolated test fixtures.
