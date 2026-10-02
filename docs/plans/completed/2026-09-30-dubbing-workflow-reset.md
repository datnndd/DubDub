# Execution Plan: Dubbing Video stage reset and Stage 1 fixes

Date: 2026-09-30

## Status

Completed

## Outcome

Each workflow stage can reset its own and dependent results without losing the uploaded media or existing exports. Deepgram with diarization validates. Stage 1 has no Denoise option and explains its controls on hover.

## Context

User-approved plan in this task; `docs/WORKFLOW.md`, `docs/webui.md`, current frontend store and screen code, project persistence, and task orchestration.

## Approach

1. Persist an untouched ASR baseline and expose a guarded project reset endpoint.
2. Apply reset semantics in the frontend and serialize autosave with reset.
3. Correct task parameter construction, remove Stage 1 Denoise, and add tooltips.
4. Prove behavior with focused backend/frontend tests and a browser workflow.

## Risks And Recovery

- Older projects may lack a recoverable ASR baseline; Stage 2 reset must fail without changing data and instruct a Stage 1 rerun.
- Keep exports on disk. Limit artifact removal to project-derived intermediate files.
- Do not reset while a project job is active; reject with 409.

## Progress

- [x] Backend reset and ASR baseline
- [x] Frontend reset and autosave ordering
- [x] ASR validation, Denoise removal, tooltips
- [x] Focused and browser validation

## Decisions

- 2026-09-30: User chose cascading invalidation, preservation of exports, and clearing a stage's choices and manual edits.
- 2026-09-30: User chose to require a Stage 1 rerun when an older project's untouched ASR transcript cannot be recovered.

## Validation

- Focused proof: `uv run --frozen pytest tests/test_stage_reset.py tests/test_orchestrator.py tests/test_webui.py tests/test_webui_projects.py tests/test_staged_asr_and_transcript.py -q` (68 passed).
- Integration or end-to-end proof: Isolated browser fixture reset a completed Stage 1, then ran ASR again; UI showed `Fresh ASR pass 2`, and persisted state advanced to Stage 2 with `forceAsr=false`.
- Repository-required checks: `bun run test` (129 passed), `bun run build` passed, and `git diff --check` passed.

## Result

All requested changes are implemented and validated locally. The browser fixture used a deterministic ASR runner; a live Deepgram API call was not made.
