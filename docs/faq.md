---
title: Frequently asked questions
description: Troubleshooting the pyVideoTrans web application and processing workflows.
---

# Frequently asked questions

## Starting the application

### How do I start the local web application?

Install the Python dependencies and build the React frontend, then run:

```powershell
uv sync
cd frontend
bun install --frozen-lockfile
bun run build
cd ..
uv run webui.py
```

The default address is `http://127.0.0.1:7860`. To select a listener and port,
use `uv run webui.py --host 0.0.0.0 --port 8080`. See [WebUI usage](webui.md)
for the supported workflow and runtime limitations.

### The server says the React build is missing. What should I do?

Build the frontend from `frontend/` using the checked-in Bun lockfile:

```powershell
bun install --frozen-lockfile
bun run build
```

The backend serves the generated `frontend/dist/` directory; source files alone
are not served as the production application.

### Which Python version and system tools are needed?

The project currently requires Python 3.10, as declared in `pyproject.toml` and
`.python-version`. Media workflows also require FFmpeg available to the
application. Provider-specific model runtimes may have additional hardware or
system requirements.

## Processing and providers

### Where can I find errors and progress?

Use the job detail/progress view in the web application. For server-side
diagnostics, inspect the console output and configured application logs. When
reporting a failure, include the job ID, selected workflow/providers, and the
relevant error context; do not include API keys or other secrets.

### Why is a job taking a long time?

Local ASR, OCR, separation, and TTS providers may download or initialize models
and can be compute-intensive. Check job progress and server logs first. Model
size, CPU/GPU availability, media duration, and selected provider all affect
runtime. API-based providers also depend on network/service response time.

### Why did a job fail before processing?

Check that the selected provider is configured and available, required model
files can be downloaded or loaded, the media is supported and readable, and
FFmpeg is available. The API validates uploaded-media identifiers and provider
configuration before starting applicable workflows.

### Where are uploaded files and generated outputs stored?

Uploads are stored in the application temporary directory. Generated files are
written under `output/`. Active jobs and uploaded-media identifiers are
process-local, so they are not restored when the server restarts. See
[WebUI usage](webui.md) for details.

### Can I resume a job after restarting the server?

No. Job records may be retained by local persistence, but execution state and
uploaded-media identifiers are in memory and active jobs do not resume after a
restart.

### Are all editing controls connected?

No. Some editing-oriented controls in the frontend are placeholders. The
current connected workflow and known limitations are listed in
[WebUI usage](webui.md).

## CLI and configuration

### Can I run workflows without the browser?

Yes. `cli.py` provides command-line workflows that reuse the shared processing
code. Run `uv run cli.py --help` to see the current arguments and
`uv run cli.py --list providers` to list registered providers.

### How do I configure provider credentials?

Use the application's settings API/UI for web workflows or the supported
configuration mechanism for CLI use. Do not put credentials in source control
or include them in bug reports.

### How do I reset local settings?

Back up the configuration files you need to keep before changing them. Settings
and database locations depend on the configured application data directory;
there is no universal safe reset command documented here.

## Getting help

If the issue persists, include the operating system, Python version, startup
command, workflow stage, provider/model selection, and a redacted error log.
Never share API keys, access tokens, or private media without permission.
