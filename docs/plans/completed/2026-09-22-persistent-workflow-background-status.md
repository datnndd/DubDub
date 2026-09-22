# Execution Plan: Persistent Video Dubbing Workflow and Background Processing Status

Date: 2026-09-22

## Status

Completed

## Outcome

Introduce persistent workflow state, crash recovery, and decoupled background task processing into `pyvideotrans` (WebUI), enabling:
1. Progress and intermediate outputs for each stage (Stage 1 Prepare/ASR, Stage 2 Review/Translation, Stage 3 Voice Dubbing, Stage 4 Video Edit/Render) to be safely persisted in SQLite (`projects.db`).
2. Users can close the browser, navigate between pages, or resume an unfinished dubbing project without re-running completed stages.
3. Multi-project concurrent background task execution with live reconnectable SSE status updates, an always-on floating HUD pill, and clean subprocess cancellation.

## Context

- Reference implementation: `VoiceStudio-0.5.0` (`backend/core/db.py`, `backend/core/tasks.py`, `backend/core/job_store.py`, `backend/api/routers/dub_export.py`, `frontend/src/components/FloatingPill.jsx`).
- Target repository: `pyvideotrans` (`webui.py`, `frontend/js/state.js`, `videotrans/task/orchestrator.py`, `videotrans/util/_ffmpeg_runner.py`).
- Architecture & Plan Artifact: `implementation_plan.md`.

## Scope

In scope:
- SQLite WAL database engine in `videotrans/core/db.py` (`projects`, `jobs`, `job_events`).
- Project and job stores (`videotrans/core/project_store.py`, `videotrans/core/job_store.py`).
- Subprocess tracking and cross-platform termination in `videotrans/core/proc_registry.py`.
- Upgraded `runffmpeg` with process registration and non-blocking cancellation.
- `aiohttp.web.StreamResponse` reconnectable SSE endpoint (`/api/jobs/{id}/stream?after_seq=N`).
- Multi-project REST endpoints (`/api/projects`, `/api/projects/{id}`, `/api/projects/{id}/resume`).
- Startup orphan sweeping (`sweep_orphans_on_startup()`).
- Content-hash audio deduplication and per-segment TTS cache checking.
- Frontend state rehydration (`activeProjectId` in `localStorage`), autosave to backend, slide-out `ProjectDrawer.js`, and interactive `FloatingPill.js`.

Out of scope:
- Rewriting Desktop Qt GUI (`sp.py`); engine in `videotrans/core/` remains UI-agnostic for future desktop consumption.
- Modifying underlying third-party neural model inference weights.

## Approach

1. **Phase 1: Engine Persistence Layer**: Implement SQLite WAL tables and stores (`db.py`, `project_store.py`, `job_store.py`).
2. **Phase 2: Subprocess Process Registry**: Implement `proc_registry.py` and upgrade `runffmpeg` to spawn `Popen` and handle process tree kill.
3. **Phase 3: WebUI Backend APIs**: Expose project management routes and SSE event streaming in `webui.py`.
4. **Phase 4: Intermediate Stage Output Serialization**: Connect orchestrator stage outputs to project artifact directory and database.
5. **Phase 5: Frontend UI & State Rehydration**: Implement `localStorage` rehydration in `state.js`, `ProjectDrawer.js`, and `FloatingPill.js`.

## Risks And Recovery

- *Risk*: Database concurrency locks during concurrent job updates.
  *Mitigation*: SQLite WAL mode with 5000ms busy timeout and thread-safe connection pooling.
- *Risk*: Orphaned FFmpeg processes on sudden server crash or task cancellation.
  *Mitigation*: Windows `taskkill /F /T /PID` and POSIX `killpg` registered in `proc_registry.py`.
- *Recovery*: All changes are modular additions in `videotrans/core/` and additive routes in `webui.py`. Frontend retains fallback polling if SSE is unsupported.

## Progress

- [x] Investigate VoiceStudio-0.5.0 and audit discrepancies with pyvideotrans.
- [x] Design target schema, SSE protocol, and process management.
- [x] Author `implementation_plan.md` and active execution plan.
- [x] Phase 1: Implement `videotrans/core/db.py`, `project_store.py`, and `job_store.py`.
- [x] Phase 2: Implement `videotrans/core/proc_registry.py` and upgrade `runffmpeg`.
- [x] Phase 3: Implement Project REST APIs and SSE streaming in `webui.py`.
- [x] Phase 4: Stage persistence and content-hash caching in orchestrator.
- [x] Phase 5: Implement `ProjectDrawer.js`, `FloatingPill.js`, and `state.js` rehydration.
- [x] Phase 6: Automated tests and manual validation.

## Decisions

- 2026-09-22: Selected hybrid SQLite document-column storage (`state_json` + queryable columns) to maintain tight synchronization with `WorkflowStore` without complex SQL joins.
- 2026-09-22: Used native `aiohttp.web.StreamResponse` for SSE streaming rather than FastAPI conventions, matching pyvideotrans's HTTP server stack.
- 2026-09-22: Designed `FloatingPill.js` as an interactive control with click-to-return and abort actions, correcting the passive HUD limitation of VoiceStudio's implementation.

## Validation

- Focused proof: Unit tests for SQLite stores and process termination (`tests/test_project_store.py`, `tests/test_job_store.py`, `tests/test_proc_registry.py`).
- Integration or end-to-end proof: SSE stream replay test, tab close/reopen state rehydration test, and multi-project background execution test (`tests/test_webui_projects.py`).
- Repository-required checks: All 45 tests passing in test suite (`tests/test_webui_projects.py`, `tests/test_project_store.py`, `tests/test_job_store.py`, `tests/test_proc_registry.py`, `tests/test_webui.py`).

## Result

All phases implemented and verified. All 45 tests pass green. Crash recovery, sequenced SSE events, project CRUD, GET /api/jobs querying, subprocess tree termination, stage output persistence into `output/projects/{project_id}/`, content-hash ASR deduplication, and UI components (`ProjectDrawer.js`, `FloatingPill.js`) are fully operational.
