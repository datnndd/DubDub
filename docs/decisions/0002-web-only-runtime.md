# 0002 Web-Only Runtime

Date: 2026-09-22

## Status

Accepted

## Context

pyVideoTrans has a browser frontend and aiohttp backend, but its shared provider
and processing paths retained dependencies on PySide6 windows, signals, global
desktop queues, and desktop packaging. That coupling makes headless deployment,
job isolation, installation, and testing unnecessarily difficult.

The repository owner approved retiring the PySide6 desktop application while
preserving useful processing and CLI behavior.

## Decision

The supported product runtime is web-oriented:

- The browser communicates with the backend through HTTP and event-stream
  interfaces. It does not call desktop implementation code.
- `webui.py`, `cli.py`, active provider registries, and shared processing
  orchestration must import and operate without PySide6 installed.
- Provider validation returns data or errors to its caller; it never opens a
  settings window.
- Per-job execution inputs and mutable state are owned by the job, not desktop
  widgets, signals, queues, or process-global UI state.
- Reusable subtitle, media, OCR, ASR, translation, TTS, dubbing, and rendering
  behavior is preserved behind UI-independent interfaces.

Desktop modules may remain temporarily during the migration plan, but they are
not allowed to become dependencies of the supported web, CLI, provider, or
shared-processing runtime.

## Alternatives Considered

1. Maintain desktop and web runtimes indefinitely. Rejected because it retains
   duplicate workflow ownership and requires PySide6 in headless deployments.
2. Hide PySide6 behind compatibility shims. Rejected because the shared engine
   would still depend on desktop concepts and failure modes.
3. Replace aiohttp, SQLite, or the frontend during the migration. Rejected
   because those replacements do not solve the Qt coupling and add risk.

## Consequences

Positive:

- Backend, CLI, and provider code can run in a headless installation.
- Job events, cancellation, errors, and options have explicit callers and
  become easier to test.
- The PySide6 dependency and desktop packaging can be removed once extraction
  and compatibility verification are complete.

Tradeoffs:

- Desktop-only utilities disappear unless their processing behavior is moved
  behind a web or CLI interface with an explicit product requirement.
- Existing settings and provider IDs need migration coverage while their UI
  metadata is removed.
- Removal must be phased so working processing logic embedded in desktop
  wrappers is not lost.

## Follow-Up

- Complete `docs/plans/active/2026-09-22-web-only-architecture-migration.md`.
- Expand no-Qt validation to the final supported package surface after desktop
  modules are removed.
- Update installation, container, CI, and architecture documentation when the
  migration is complete.
