# Dubbing Video WebUI

The WebUI serves the frontend in `frontend/` and connects it to the existing
video translation and dubbing workflow.

## Start

```powershell
uv run webui.py
```

The default address is `http://127.0.0.1:7860`. Use `--host` and `--port`
to change the listener:

```powershell
uv run webui.py --host 0.0.0.0 --port 8080
```

## Supported workflow

- Upload one video or audio file and inspect its duration, size, streams,
  resolution, frame rate, and codecs before creating a task.
- Choose source and target languages, recognition, translation, TTS, model,
  voice, noise removal, diarization, and voice pace.
- Start one in-process job from the inspected media and observe stage/progress
  updates. The server rejects duplicate active jobs for the same upload.
- Cancel the active job.
- Preview and download outputs reported by the task runner.

Jobs are held in memory and do not resume after the server restarts.
Uploaded-media identifiers are also in-memory and are validated by the server;
frontend-provided paths are never accepted.

## Placeholder controls

The transcript/OCR review, per-segment voice regeneration, timeline editing,
lip-sync, inpainting, face retouching, and 4K enhancement controls are retained
from the new frontend design but are not connected to backend behavior yet.
They require explicit checkpoint or editing interfaces before implementation.

## Local data

- Uploaded media is stored under the application temporary directory.
- Generated files are written under `output/`.
- Output download endpoints expose only files returned by the task runner.
