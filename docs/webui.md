# Dubbing Video WebUI

The WebUI serves the frontend in `frontend/` and connects it to the existing
video translation and dubbing workflow.

## Start

### Development Mode (with hot-reload)
```powershell
bun run dev
```

### Production Mode (single-port serving)
```powershell
bun run build
uv run python webui.py
```

The default address is `http://127.0.0.1:7860`. Use `--host` and `--port`
to change the listener:

```powershell
uv run python webui.py --host 0.0.0.0 --port 7860
```

## Supported workflow

- Upload one video or audio file and inspect its duration, size, streams,
  resolution, frame rate, and codecs before creating a task.
- Choose source and target languages, recognition, translation, TTS, model,
  voice, diarization, and voice pace. Stage 1 controls explain their effect on hover.
- Start one in-process job from the inspected media and observe stage/progress
  updates. The server rejects duplicate active jobs for the same upload.
- Cancel the active job.
- Preview and download outputs reported by the task runner.
- In Stage 2, export a translated SRT directly after every segment has target
  text. This does not generate voice audio or advance the workflow.
- In Stage 2, check segments and choose Run OCR on Selected Segments to recognize subtitles only
  within each checked segment's time range. The crop dialog shows a result or
  error for each range; successful text immediately replaces the matching source
  subtitle and updates the project's UTF-8 source SRT.
  OCR Extract on an individual segment remains available. Changed source text
  clears only that segment's translation and generated voice preview.
- Reset any stage to clear its choices and dependent results while keeping the
  uploaded media, earlier stages, and previously exported files.
- In Stage 3, generate and audition each dubbed voice preview. The video preview
  mutes the source track and plays generated segment audio where available.
  Each preview shows its applied speed. Stage 4 controls the final audio mix.
- Opening Stage 4 assembles the generated voice previews at their subtitle times.
  The editor plays this track with the video and lets you adjust its volume.
- The CapCut package contains two subtitle files and the merged voiceover. Use
  the original video already on your computer when importing into CapCut.

Jobs are held in memory and do not resume after the server restarts.
Uploaded-media identifiers are also in-memory and are validated by the server;
frontend-provided paths are never accepted.

## Placeholder controls

The timeline editing,
lip-sync, inpainting, face retouching, and 4K enhancement controls are retained
from the new frontend design but are not connected to backend behavior yet.
They require explicit checkpoint or editing interfaces before implementation.

## Local data

- Uploaded media is stored under the application temporary directory.
- Generated files are written under `output/`.
- Output download endpoints expose only files returned by the task runner.
