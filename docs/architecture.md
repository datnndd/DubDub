# Web application architecture

pyVideoTrans is a Python media-processing application exposed through a React
frontend, a FastAPI API (served via Uvicorn), and a command-line entry point. The supported web
runtime is intentionally independent of desktop UI frameworks. See
[ADR 0002](decisions/0002-web-only-runtime.md) for the accepted web-only
boundary.

## Runtime boundaries

```text
React frontend (frontend/src)
        │ HTTP / JSON / server-sent events
        ▼
FastAPI application (videotrans/api)
        │ route adapters and Pydantic request validation
        ▼
Application services (videotrans/core)
  jobs · projects · media/assets · persistence
        │ typed requests, events, cancellation
        ▼
Workflow and processing (videotrans/task, videotrans/process)
  prepare · ASR · OCR · translate · TTS · align · render
        │
        ├── Provider registries (recognition, ocr, translator, tts)
        └── Media utilities and external tools (ffmpeg, model runtimes)
```

`webui.py` is the web server launcher (using Uvicorn). `cli.py` is the command-line entry
point. Both use the shared processing workflows; neither relies on a desktop
event loop. The browser communicates only through API contracts and does not
import or invoke Python implementation modules.

## API and application services

`videotrans/api/app.py` builds the FastAPI application, injects runtime
services, registers route modules, and serves the built React bundle. Route
modules under `videotrans/api/routes/` adapt HTTP requests and responses; they
should not own long-running media processing or persistence policy.

`videotrans/core/` owns application-level services and persistence, including
job execution and lifecycle, job/project stores, media and edit-asset stores,
and voice configuration. Jobs emit structured events and expose progress,
outputs, and cancellation to API clients. Job state is persisted locally, but
active execution and uploaded-media identifiers are process-local; jobs do not
resume after a server restart.

## Workflow and providers

`videotrans/task/orchestrator.py` is the UI-independent workflow boundary. It
accepts task inputs, emits structured events, returns results, and observes a
cancellation token. Stage-specific task modules retain the existing media and
subtitle processing behavior. Processing is selected from the request and
workflow flags rather than from frontend state or widget objects.

ASR, OCR, translation, and TTS packages expose provider registries and load
provider implementations on demand. This keeps optional model/service imports
out of unrelated paths while preserving a common provider interface. Media
operations, subtitle handling, and subprocess execution remain reusable shared
logic rather than web-route code.

## Frontend and deployment

The React source and its tests live in `frontend/`. Build it with the frontend
lockfile before starting a production server; the backend serves
`frontend/dist/`. Development reload mode refreshes the browser when frontend
files change; it is not hot-module replacement. The default local server is
`http://127.0.0.1:7860`.

Jobs and uploaded-media references are currently held in memory for active
runtime coordination. SQLite-backed stores retain job/project records, and
generated outputs are written below `output/`. Uploaded media is placed in an
application temporary directory. API routes validate server-issued media and
asset identifiers; clients do not choose arbitrary filesystem paths.

## Design constraints

- Keep HTTP parsing, workflow policy, provider execution, media processing,
  and persistence in their respective layers.
- Preserve shared processing behavior when changing a UI or API adapter.
- Keep request/event/result contracts independent of FastAPI and React where
  practical so the same workflows can be exercised by CLI and tests.
- Supported web, CLI, provider, and processing imports must work without
  PySide6. Historical migration notes may mention the retired desktop runtime;
  current setup guidance should not describe it as supported.

## Current limitations

Some editing-oriented frontend controls are still placeholders rather than
connected workflow capabilities. Job execution is in-process and does not
survive server restarts. These limitations are documented in
[WebUI usage](webui.md) and should be revised when observable behavior changes.
