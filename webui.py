"""Local WebUI server for the Dubbing Video workflow."""

from __future__ import annotations

import argparse
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote

from aiohttp import web

from videotrans.configure import config as runtime_config

runtime_config.init_run()

from videotrans import recognition, translator, tts
from videotrans.configure.config import ROOT_DIR, TEMP_DIR, app_cfg
from videotrans.configure.contants import AUDIO_EXITS, FASTER_MODELS_DICT, VIDEO_EXTS
from videotrans.task.orchestrator import (
    CancellationToken,
    EventKind,
    TaskEvent,
    TaskRequest,
    TaskStatus,
    run,
)
from videotrans.util._ffmpeg_misc import format_video
from videotrans.util._ffprobe import get_video_info
from videotrans.util.gpus import getset_gpu
from videotrans.util.help_role import role_menu


FRONTEND_DIR = Path(ROOT_DIR) / "frontend"
UPLOAD_DIR = Path(TEMP_DIR) / "webui_uploads"
OUTPUT_DIR = Path(ROOT_DIR) / "output"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class JobRecord:
    id: str
    token: CancellationToken
    status: str = "queued"
    stage: str | None = None
    progress: float | None = None
    message: str = "Queued"
    events: list[dict[str, Any]] = field(default_factory=list)
    outputs: tuple[Path, ...] = ()
    error: str | None = None
    media_id: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def accept(self, event: TaskEvent) -> None:
        item = {
            "kind": event.kind.value,
            "stage": event.stage,
            "message": event.message,
            "progress": event.progress,
            "details": dict(event.details),
        }
        with self._lock:
            self.events.append(item)
            self.events[:] = self.events[-200:]
            self.stage = event.stage
            if event.progress is not None:
                self.progress = event.progress
            if event.message:
                self.message = event.message
            if event.kind in {EventKind.RUNNING, EventKind.STAGE_STARTED}:
                self.status = "running"

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "id": self.id,
                "status": self.status,
                "stage": self.stage,
                "progress": self.progress,
                "message": self.message,
                "events": list(self.events),
                "error": self.error,
                "outputs": [
                    {"name": path.name, "url": f"/api/jobs/{self.id}/outputs/{index}"}
                    for index, path in enumerate(self.outputs)
                ],
            }


class JobManager:
    def __init__(self, runner: Callable = run) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._active_by_media: dict[str, str] = {}
        self._lock = threading.Lock()
        self._runner = runner

    def submit(self, params: dict[str, Any], *, media_id: str) -> JobRecord:
        with self._lock:
            active_id = self._active_by_media.get(media_id)
            if active_id:
                raise ActiveJobError(f"Media already running in job {active_id}")
            job = JobRecord(uuid.uuid4().hex, CancellationToken(), media_id=media_id)
            self._jobs[job.id] = job
            self._active_by_media[media_id] = job.id
        threading.Thread(target=self._execute, args=(job, params), daemon=True).start()
        return job

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> JobRecord | None:
        job = self.get(job_id)
        if job:
            job.token.cancel()
        return job

    def _execute(self, job: JobRecord, params: dict[str, Any]) -> None:
        try:
            result = self._runner(TaskRequest(params), job.accept, job.token)
            with job._lock:
                job.status = result.status.value
                job.outputs = result.outputs
                if result.status == TaskStatus.SUCCEEDED:
                    job.message = "Processing complete"
                    job.progress = 100.0
                elif result.status == TaskStatus.CANCELLED:
                    job.message = "Processing cancelled"
                else:
                    job.error = result.failure.message if result.failure else "Processing failed"
                    job.message = job.error
        finally:
            with self._lock:
                if self._active_by_media.get(job.media_id) == job.id:
                    self._active_by_media.pop(job.media_id, None)


class ActiveJobError(RuntimeError):
    """Raised when the same ingested media already has an active job."""


@dataclass(frozen=True)
class MediaRecord:
    id: str
    path: Path
    filename: str
    size_bytes: int
    info: dict[str, Any]

    def snapshot(self) -> dict[str, Any]:
        width = int(self.info.get("width", 0) or 0)
        height = int(self.info.get("height", 0) or 0)
        return {
            "id": self.id,
            "filename": self.filename,
            "sizeBytes": self.size_bytes,
            "durationMs": int(self.info.get("time", 0) or 0),
            "resolution": f"{width}x{height}" if width and height else None,
            "fps": float(self.info.get("video_fps", 0) or 0),
            "videoCodec": self.info.get("video_codec_name") or None,
            "audioCodec": self.info.get("audio_codec_name") or None,
            "hasVideo": bool(self.info.get("video_streams")),
            "hasAudio": bool(self.info.get("streams_audio")),
        }


class MediaStore:
    def __init__(self, upload_dir: Path, probe: Callable[[str | Path], dict[str, Any]]) -> None:
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._probe = probe
        self._records: dict[str, MediaRecord] = {}
        self._lock = threading.Lock()

    def inspect(self, path: Path, filename: str) -> MediaRecord:
        info = self._probe(path)
        if not info.get("video_streams") and not info.get("streams_audio"):
            raise ValueError("The selected file contains no readable media streams")
        record = MediaRecord(uuid.uuid4().hex, path, filename, path.stat().st_size, info)
        with self._lock:
            self._records[record.id] = record
        return record

    def get(self, media_id: str) -> MediaRecord | None:
        with self._lock:
            return self._records.get(media_id)


JOBS = JobManager()
MEDIA = MediaStore(UPLOAD_DIR, get_video_info)


def _required_index(value: Any, size: int, label: str) -> int:
    try:
        index = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"A valid {label} is required") from None
    if not 0 <= index < size:
        raise ValueError(f"Unknown {label}: {value}")
    return index


def _optional_index(value: Any, size: int, default: int = 0) -> int:
    try:
        index = int(value)
    except (TypeError, ValueError):
        return default
    return index if 0 <= index < size else default


def build_task_params(input_path: Path, options: dict[str, Any]) -> dict[str, Any]:
    """Translate supported frontend fields into the existing task configuration."""
    file_info = format_video(input_path.resolve().as_posix())
    safe_stem = re.sub(r"[^\w.-]+", "-", file_info.basename, flags=re.UNICODE).strip("-")
    target_dir = OUTPUT_DIR / (safe_stem or file_info.uuid)
    cache_dir = Path(TEMP_DIR) / file_info.uuid

    recogn_type = _required_index(options.get("recognType"), len(recognition.RECOGN_NAME_LIST), "ASR engine")
    translate_type = _required_index(options.get("translateType"), len(translator.TRANSLASTE_NAME_LIST), "translation engine")
    tts_type = _required_index(options.get("ttsType", 0), len(tts.TTS_NAME_LIST), "voice engine")
    source_language = str(options.get("sourceLanguage") or "")
    target_language = str(options.get("targetLanguage") or "")
    if source_language not in translator.LANGNAME_DICT:
        raise ValueError(f"Unknown source language: {source_language or 'missing'}")
    if target_language not in translator.LANGNAME_DICT:
        raise ValueError(f"Unknown target language: {target_language or 'missing'}")
    voice_role = str(options.get("voiceRole") or "")
    if not voice_role:
        try:
            voice_role = next((voice for voice in role_menu(tts_type, langcode=target_language) if voice != "No"), "No")
        except Exception:
            voice_role = "No"

    params = asdict(file_info)
    params.update({
        "name": input_path.resolve().as_posix(),
        "target_dir": target_dir.resolve().as_posix(),
        "cache_folder": cache_dir.resolve().as_posix(),
        "source_language_code": source_language,
        "target_language_code": target_language,
        "recogn_type": recogn_type,
        "model_name": str(options.get("modelName") or "large-v3-turbo"),
        "translate_type": translate_type,
        "tts_type": tts_type,
        "voice_role": voice_role,
        "is_cuda": bool(options.get("useCuda", False)),
        "remove_noise": bool(options.get("removeNoise", True)),
        "enable_diariz": bool(options.get("speakerDiarization", False)),
        "nums_diariz": int(options.get("speakerCount", 0) or 0),
        "voice_rate": str(options.get("voiceRate") or "+0%"),
        "volume": "+0%",
        "pitch": "+0Hz",
        "voice_autorate": True,
        "video_autorate": False,
        "align_sub_audio": True,
        "subtitle_type": 1,
        "clear_cache": True,
        "embed_bgm": True,
    })
    return params


async def options_handler(_request: web.Request) -> web.Response:
    languages = [{"code": code, "name": name} for code, name in translator.LANGNAME_DICT.items()]
    return web.json_response({
        "languages": languages,
        "recognizers": list(enumerate(recognition.RECOGN_NAME_LIST)),
        "translators": list(enumerate(translator.TRANSLASTE_NAME_LIST)),
        "voices": list(enumerate(tts.TTS_NAME_LIST)),
        "models": list(FASTER_MODELS_DICT.keys()),
    })


async def voices_handler(request: web.Request) -> web.Response:
    tts_type = _optional_index(request.query.get("ttsType"), len(tts.TTS_NAME_LIST))
    language = request.query.get("language", "")
    try:
        voices = role_menu(tts_type, langcode=language) or ["No"]
    except Exception:
        voices = ["No"]
    return web.json_response({"voices": voices})


async def media_handler(request: web.Request) -> web.Response:
    reader = await request.multipart()
    upload_path: Path | None = None
    filename = ""
    store: MediaStore = request.app["media_store"]
    async for part in reader:
        if part.name == "file" and part.filename:
            filename = Path(unquote(part.filename)).name
            extension = Path(filename).suffix.lower().lstrip(".")
            if extension not in {*VIDEO_EXTS, *AUDIO_EXITS}:
                raise web.HTTPBadRequest(text=f"Unsupported media type: .{extension or 'unknown'}")
            upload_path = store.upload_dir / f"{uuid.uuid4().hex}-{filename}"
            with upload_path.open("wb") as output:
                while chunk := await part.read_chunk():
                    output.write(chunk)
    if upload_path is None or not upload_path.is_file():
        raise web.HTTPBadRequest(text="A video or audio file is required")

    try:
        media = store.inspect(upload_path, filename)
    except Exception as exc:
        upload_path.unlink(missing_ok=True)
        raise web.HTTPBadRequest(text=f"Unable to read media: {exc}") from exc
    return web.json_response(media.snapshot(), status=201)


async def create_job_handler(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(text="A JSON job request is required") from exc
    media_id = str(payload.get("mediaId") or "")
    options = payload.get("options")
    if not isinstance(options, dict):
        raise web.HTTPBadRequest(text="Job options are required")
    media_store: MediaStore = request.app["media_store"]
    media = media_store.get(media_id)
    if media is None or not media.path.is_file():
        raise web.HTTPBadRequest(text="Select and inspect a media file before starting")

    try:
        params = build_task_params(media.path, options)
        getset_gpu()
        manager: JobManager = request.app["job_manager"]
        job = manager.submit(params, media_id=media.id)
    except ActiveJobError as exc:
        raise web.HTTPConflict(text=str(exc)) from exc
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    return web.json_response(job.snapshot(), status=202)


async def job_handler(request: web.Request) -> web.Response:
    job = request.app["job_manager"].get(request.match_info["job_id"])
    if not job:
        raise web.HTTPNotFound(text="Job not found")
    return web.json_response(job.snapshot())


async def cancel_job_handler(request: web.Request) -> web.Response:
    job = request.app["job_manager"].cancel(request.match_info["job_id"])
    if not job:
        raise web.HTTPNotFound(text="Job not found")
    return web.json_response(job.snapshot())


async def output_handler(request: web.Request) -> web.StreamResponse:
    job = request.app["job_manager"].get(request.match_info["job_id"])
    if not job:
        raise web.HTTPNotFound(text="Job not found")
    try:
        output = job.outputs[int(request.match_info["index"])]
    except (ValueError, IndexError):
        raise web.HTTPNotFound(text="Output not found")
    if not output.is_file():
        raise web.HTTPNotFound(text="Output no longer exists")
    return web.FileResponse(output, headers={"Content-Disposition": f'attachment; filename="{output.name}"'})


async def index_handler(_request: web.Request) -> web.StreamResponse:
    return web.FileResponse(FRONTEND_DIR / "index.html")


def create_app(
    *,
    job_manager: JobManager | None = None,
    upload_dir: Path | None = None,
    media_probe: Callable[[str | Path], dict[str, Any]] = get_video_info,
) -> web.Application:
    if not (FRONTEND_DIR / "index.html").is_file():
        raise RuntimeError(f"Frontend not found: {FRONTEND_DIR}")
    app = web.Application(client_max_size=20 * 1024 ** 3)
    app["job_manager"] = job_manager or JOBS
    app["media_store"] = MEDIA if upload_dir is None and media_probe is get_video_info else MediaStore(upload_dir or UPLOAD_DIR, media_probe)
    app.router.add_get("/", index_handler)
    app.router.add_get("/api/options", options_handler)
    app.router.add_get("/api/voices", voices_handler)
    app.router.add_post("/api/media", media_handler)
    app.router.add_post("/api/jobs", create_job_handler)
    app.router.add_get("/api/jobs/{job_id}", job_handler)
    app.router.add_post("/api/jobs/{job_id}/cancel", cancel_job_handler)
    app.router.add_get("/api/jobs/{job_id}/outputs/{index}", output_handler)
    app.router.add_static("/css", FRONTEND_DIR / "css")
    app.router.add_static("/js", FRONTEND_DIR / "js")
    app.router.add_static("/assets", FRONTEND_DIR / "assets")
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="pyVideoTrans Dubbing Video WebUI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    app_cfg.exec_mode = "web"
    web.run_app(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
