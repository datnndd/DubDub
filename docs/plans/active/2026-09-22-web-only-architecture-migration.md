# Execution Plan: Web-Only Architecture Migration

Date: 2026-09-22

## Status

Active

## Outcome

Transform pyVideoTrans from a mixed PySide6/web application into a web-oriented
application whose browser UI and CLI use the same UI-independent processing
engine. Remove PySide6, desktop entry points, desktop packaging, obsolete
support code, and verified dead dependencies while preserving useful ASR,
translation, TTS, OCR, subtitle, audio, video, project, and CLI behavior.

Completion requires observable browser, API, CLI, persistence, cancellation,
and representative media-processing proof from a clean environment without
PySide6 installed.

## Context

- Owner approval: conversation on 2026-09-22 approving the repository audit and
  proposed phased migration.
- Repository workflow: `AGENTS.md` and `docs/WORKFLOW.md`.
- Current architecture description: `docs/ARCHITECTURE.md`.
- Accepted OCR behavior: `docs/decisions/0001-video-ocr-as-subtitle-source.md`.
- Current browser/backend entry points: `frontend/`, `webui.py`.
- Current shared processing seam: `videotrans/task/orchestrator.py` and
  `videotrans/task/trans_create.py`.
- Current persistence/job work: `videotrans/core/` and
  `docs/plans/completed/2026-09-22-persistent-workflow-background-status.md`.
- The worktree contained pre-existing uncommitted persistence, frontend, job,
  cancellation, and orchestration changes when this plan started. Preserve and
  validate those changes; do not overwrite or attribute them to this migration.

## Scope

In scope:

- Retire `sp.py` and the PySide6 desktop application.
- Remove Qt UI packages, workers, signals, dialogs, assets, packaging, settings,
  tests, and dependencies after useful processing behavior is extracted.
- Make provider validation and execution independent of desktop windows.
- Replace per-job global runtime state with explicit job-owned inputs and
  execution state.
- Preserve active providers and reusable media/subtitle processing.
- Give one application workflow owner responsibility for job lifecycle,
  persistence, cancellation, events, and artifacts.
- Split HTTP transport, application workflows, providers, media processing,
  persistence, jobs, configuration, and domain data along explicit seams.
- Simplify frontend job updates and preserve Stage 1 through Stage 4 behavior.
- Remove only code and dependencies proved obsolete after dynamic registry,
  configuration migration, and behavior checks.
- Update CLI, container, CI, installation, and architecture documentation for
  the web-oriented product.

Out of scope:

- Replacing aiohttp, SQLite, the current JavaScript frontend, FFmpeg, or ML
  provider implementations solely for architectural style.
- Upgrading Python or changing model weights during this migration.
- Rebuilding every retired desktop utility as a browser feature without a
  separate product requirement.
- Deleting downloaded models, reference audio, projects, outputs, credentials,
  or other user data.

## Approach

Work in vertical, behavior-preserving slices through these approved seams:

1. Browser/HTTP workflow, especially Stage 2 translation to Stage 3.
2. Shared `TaskRequest`/event/result processing runner.
3. Provider validation and invocation.
4. Job persistence, event replay, cancellation, and artifact recovery.
5. CLI entry points.

Sequence:

1. Record the dirty baseline and run focused current tests.
2. Add missing behavior tests at the approved seams before changing them.
3. Remove Qt imports from shared/provider paths and return structured errors.
4. Make job-specific state, cancellation, events, paths, and voice assignments
   explicit while retaining process-wide model/codec caches where appropriate.
5. Consolidate lifecycle and persistence ownership outside HTTP handlers and
   processing stages.
6. Split `webui.py` and frontend state incrementally behind existing routes and
   observable behavior.
7. Delete retired desktop code and dependencies only after no-Qt proof passes.
8. Move remaining modules in small groups, updating dynamic provider registry
   strings and compatibility imports with each verified group.
9. Prune verified dead code and direct dependencies, then update deployment and
   documentation.

Prefer a small number of deep modules. Do not add interfaces for hypothetical
variation, an ORM, a second job framework, or pass-through packages.

## Risks And Recovery

- Dynamic provider imports can evade static analysis. Exercise every registered
  provider import and configuration path before deleting or moving modules.
- Existing projects and settings can contain legacy provider IDs and paths.
  Preserve migrations and validate representative old fixtures.
- Global runtime state can leak between concurrent jobs. Add concurrency tests
  before removing fallbacks.
- Media/GPU behavior is expensive to prove. Use small local fixtures first and
  run explicitly configured CPU/GPU/provider smoke tests before completion.
- File moves can obscure behavior changes. Keep behavior edits, moves, and
  deletions in separate reviewable groups.
- Recover by reverting the current coherent group only. Preserve compatibility
  imports until all callers and tests move; do not delete user data or caches.

## Progress

- [x] Audit repository structure, desktop code, dependencies, coupling, tests,
  dead-code candidates, and target architecture.
- [x] Obtain owner approval for the target and phased migration.
- [x] Create this active execution plan and record the pre-existing dirty state.
- [x] Phase 0: run and record focused baseline proof and known failures.
- [ ] Phase 1: protect Stage 2-to-3, voice propagation, provider-error,
  cancellation, restart, and render behavior at approved seams.
- [ ] Phase 2: remove shared/provider dependencies on Qt dialogs and signals.
- [ ] Phase 3: isolate job execution state from global `app_cfg`.
- [ ] Phase 4: consolidate job lifecycle, persistence, events, and artifacts.
- [ ] Phase 5: split HTTP and frontend state behind compatible interfaces.
- [ ] Phase 6: remove PySide6 application code, packaging, tests, and dependencies.
- [ ] Phase 7: reorganize modules and prune verified dead code.
- [ ] Phase 8: simplify dependencies and update CI, container, and documentation.
- [ ] Run clean no-Qt, browser, CLI, restart, CPU media, and configured-provider
  verification; record remaining GPU/provider limits.

## Decisions

- 2026-09-22: The owner approved retiring the PySide6 desktop application while
  preserving reusable processing and the CLI.
- 2026-09-22: Keep aiohttp, SQLite, and the current JavaScript frontend; no
  framework rewrite is needed to achieve the requested architecture.
- 2026-09-22: Treat HTTP/browser workflows, the shared runner, provider
  validation, job lifecycle, and CLI as the public test seams.
- 2026-09-22: Use explicit job-owned state for mutable execution data; retain
  deliberate process-wide caches separately.
- 2026-09-22: Remove code only after observable behavior has moved and passed at
  its new seam. Static no-caller results identify candidates, not final proof.
- 2026-09-22: Provider validation returns actionable messages and never opens a
  desktop settings window. Presentation of configuration errors belongs to the
  browser or CLI caller.
- 2026-09-22: Segment/speaker voice assignments are job input (`line_roles`),
  not process-global `app_cfg` state.

Promote lasting module dependency rules into an ADR before encoding a permanent
architecture invariant.

## Validation

- Baseline proof (2026-09-22): the first focused run produced 77 passes and
  five non-executed async tests because `pytest-asyncio` was not declared. After
  adding that development dependency and refreshing `uv.lock`, the identical
  command completed with 82 passes. The remaining 146 warnings are primarily
  aiohttp `AppKey` recommendations and upstream package deprecations.
- Migration checkpoint (2026-09-22): provider execution now carries event and
  cancellation context through ASR, translation, and TTS; provider validation
  has no window metadata or winform calls; render parameters carry per-line
  voice assignments. The combined affected suite passed 170 tests.
- Focused proof: provider registry/validation, subtitle/media transformations,
  orchestrator, SQLite stores, event replay, cancellation, frontend state, and
  CLI tests using `uv run --frozen pytest` plus Node checks where applicable.
- Integration proof: Stage 1 ASR through Stage 4 render, Stage 2 translation to
  Stage 3 population, voice propagation, project close/reopen, server restart,
  and job cancellation with small local fixtures.
- Clean-environment proof: install and import backend/CLI without PySide6; scan
  reachable shared/backend modules for forbidden Qt imports.
- Provider/media proof: opt-in configured provider calls and representative CPU
  render; configured GPU smoke test when hardware is available.
- Deployment proof: container startup/readiness and repository CI commands.
- Repository-required checks: keep this plan current and do not move it to
  `completed/` until all required proof is observed.

## Result

In progress. No desktop code has been removed yet. The initial repository audit
and owner approval establish the migration direction; implementation and
behavior proof remain to be completed phase by phase.
