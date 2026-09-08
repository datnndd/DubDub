# OCR workspace and Prepare review

Date: 2026-09-07

## Status

Complete

## Outcome and authority

Owner request: the upload OCR button opens a surface showing the OCR model,
an adjustable region on video, Start, live progress and estimated remaining
time; completion automatically opens Prepare for reviewing OCR results before
continuing the existing dubbing flow. Follow CLAUDE.md localization/local-first
rules and preserve the previous OCR repair and other working-tree edits.

## Approach

- [x] Show RapidOCR and optional PaddleOCR metadata without downloading/loading weights.
- [x] Add region move/resize and keyboard-accessible coordinate controls.
- [x] Connect real progress stages, frame counts, live text and measured ETA.
- [x] Add Prepare review and explicit continuation to the existing editor.
- [x] Add locale keys, tests, build verification and documentation.

## Decisions and risks

- Use existing UI primitives with RapidOCR as the ready default and PaddleOCR as
  an explicit optional model. No required network calls are introduced.
- ETA is an estimate for frame recognition, unavailable during upload/model load
  and other stages without a measured denominator. Never invent progress.
- Keep Prepare review separate from ASR; reviewing OCR must not retranscribe.
- Reuse existing segment storage and downstream dubbing handlers.
- Focused pytest/Vitest and isolated browser verification; no merge/release.

## Validation and result

Frontend typecheck/build and targeted Vitest pass. Backend OCR tests pass where the
host has the optional audio dependency; remaining failures are environment setup
(`soundfile` unavailable) and pre-existing temporary-directory permissions.
