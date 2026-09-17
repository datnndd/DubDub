# Execution Plan: Dubbing Video Frontend Integration

Date: 2026-09-16

## Status

Completed

## Outcome

The new `frontend/` application is the only WebUI for Dubbing Video and can upload media, configure supported backend options, run/cancel processing, display progress, and download outputs through the existing orchestration module.

## Context

`frontend/` is currently a static four-stage mockup with placeholder data. `webui.py` is the old Gradio frontend and already calls the UI-independent task runner. The runner supports complete noninteractive jobs but not interactive mid-pipeline checkpoints.

## Scope

In scope:

- Replace Gradio serving with a local aiohttp server for the new static frontend and a small job adapter.
- Connect media upload, supported configuration, progress, cancellation, errors, and outputs.
- Preserve unsupported Stage 2–4 controls as visual/local-state placeholders.
- Replace old Gradio-specific tests and documentation.

Out of scope:

- Interactive transcript checkpointing, per-segment voice regeneration, NLE editing, lip sync, 4K enhancement, and persistent/restart-resumable jobs.

## Approach

Serve the existing frontend and JSON endpoints from `webui.py`. Keep processing in `videotrans.task.orchestrator`; the WebUI adapter owns only upload storage and in-memory job lifecycle. Bind existing UI controls to the supported request fields and poll job state for progress.

## Risks And Recovery

- Uploaded files remain under the application temp directory and output downloads are restricted to paths returned by the runner.
- One process owns in-memory jobs; restart recovery remains explicitly unsupported.
- Recovery is restoring the previous `webui.py`; backend orchestration remains independent.

## Progress

- [x] Map new frontend controls to existing backend capabilities.
- [x] Replace the old frontend server and add job endpoints.
- [x] Bind supported new-frontend controls and preserve placeholders.
- [x] Replace validation and documentation, then run focused and observable proof.

## Decisions

- 2026-09-16: A complete backend run starts from Stage 1; Stages 2–4 remain local preview/edit placeholders until checkpoint interfaces exist.
- 2026-09-16: Job state is in-memory and output access is limited to runner-reported files.

## Validation

- Focused proof: 97 WebUI, orchestration, CLI, and dubbed-output tests passed.
- Integration proof: an isolated server served the real page and populated 35 languages, 27 recognition providers, 25 translators, 35 TTS providers, and 19 models; the instance was then stopped.
- Repository checks: Python compilation, all frontend JavaScript syntax checks, and `git diff --check` passed. Full pytest collection remains blocked by the pre-existing missing `videotrans.task.job._get_type_name` imported by `tests/test_job_helpers.py`.

## Result

The new frontend is now the sole Dubbing Video WebUI. Its supported controls use the existing task runner through an aiohttp upload/job adapter with progress polling, scoped cancellation, and restricted output downloads. Unsupported mid-pipeline editing controls remain present but unconnected as explicitly requested.
