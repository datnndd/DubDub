"""Local WebUI server for the Dubbing Video workflow."""

from __future__ import annotations

import argparse
import asyncio
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable
from urllib.parse import unquote

from aiohttp import web

from videotrans.configure import config as runtime_config

runtime_config.init_run()

from videotrans import recognition, translator, tts
from videotrans.configure.config import ROOT_DIR, TEMP_DIR, app_cfg, params as app_params
from videotrans.configure.contants import AUDIO_EXITS, VIDEO_EXTS
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
from videotrans.configure.excepts import get_msg_from_except
from videotrans.util.gpus import getset_gpu
from videotrans.util.help_misc import process_openai_api
from videotrans.util.help_role import role_menu


FRONTEND_DIR = Path(ROOT_DIR) / "frontend"
UPLOAD_DIR = Path(TEMP_DIR) / "webui_uploads"
OUTPUT_DIR = Path(ROOT_DIR) / "output"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


ASR_PROVIDERS = (
    {
        "id": "qwen-asr",
        "label": "Qwen-ASR",
        "recognType": recognition.QWENASR,
        "models": ("1.7B", "0.6B"),
    },
    {
        "id": "deepgram",
        "label": "Deepgram",
        "recognType": recognition.Deepgram,
        "models": tuple(recognition.get_model_by_type(recognition.Deepgram)),
        "settingsKey": "deepgram_apikey",
        "thirdParty": True,
    },
    {
        "id": "gemini-stt",
        "label": "Gemini STT",
        "recognType": recognition.GEMINI_SPEECH,
        "models": ("gemini-flash-latest",),
        "settingsKey": "gemini_key",
        "thirdParty": True,
    },
    {
        "id": "google-stt",
        "label": "Google STT API",
        "recognType": recognition.GOOGLE_SPEECH,
        "models": ("google-web-speech",),
        "thirdParty": True,
    },
    {
        "id": "elevenlabs",
        "label": "ElevenLabs",
        "recognType": recognition.ElevenLabs,
        "models": ("scribe_v2",),
        "settingsKey": "elevenlabstts_key",
        "thirdParty": True,
    },
    {
        "id": "whisper-large-v3",
        "label": "Whisper Large-v3",
        "recognType": recognition.FASTER_WHISPER,
        "models": ("large-v3",),
    },
)
ASR_BY_TYPE = {provider["recognType"]: provider for provider in ASR_PROVIDERS}
ASR_BY_ID = {provider["id"]: provider for provider in ASR_PROVIDERS}
TIMING_MODES = {
    "voice": {"voice_autorate": True, "video_autorate": False, "align_sub_audio": False},
    "video": {"voice_autorate": False, "video_autorate": True, "align_sub_audio": False},
    "align": {"voice_autorate": False, "video_autorate": False, "align_sub_audio": True},
}
TRANSLATION_MODES = {
    "line": {
        "label": "Line-by-line",
        "description": "Send plain subtitle text in batches.",
        "aisendsrt": False,
    },
    "srt": {
        "label": "Send SRT",
        "description": "Send subtitle blocks with timestamps and structure.",
        "aisendsrt": True,
    },
}
TRANSLATION_PROVIDERS = (
    {
        "id": "google",
        "label": "Google Translate",
        "translateType": translator.GOOGLE_INDEX,
    },
    {
        "id": "openai",
        "label": "OpenAI ChatGPT",
        "translateType": translator.CHATGPT_INDEX,
        "baseUrlKey": "chatgpt_api",
        "defaultBaseUrl": "https://api.openai.com/v1",
        "keyKey": "chatgpt_key",
        "modelKey": "chatgpt_model",
    },
    {
        "id": "gemini",
        "label": "Gemini",
        "translateType": translator.GEMINI_INDEX,
        "baseUrlKey": "gemini_api",
        "defaultBaseUrl": "",
        "keyKey": "gemini_key",
        "modelKey": "gemini_model",
    },
    {
        "id": "deepseek",
        "label": "DeepSeek",
        "translateType": translator.DEEPSEEK_INDEX,
        "baseUrlKey": "deepseek_api",
        "defaultBaseUrl": "https://api.deepseek.com/v1",
        "keyKey": "deepseek_key",
        "modelKey": "deepseek_model",
    },
)
TRANSLATION_BY_TYPE = {provider["translateType"]: provider for provider in TRANSLATION_PROVIDERS}
TRANSLATION_BY_ID = {provider["id"]: provider for provider in TRANSLATION_PROVIDERS}


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


def run_prepare_review(
    request: TaskRequest,
    event_sink: Callable[[TaskEvent], None] | None = None,
    cancellation_token: CancellationToken | None = None,
):
    """Run only the stages needed to produce a transcript for Review Transcript."""
    return run(
        request,
        event_sink,
        cancellation_token,
        stop_after_stage="diariz",
    )


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
            "container": self.info.get("format_name") or None,
            "bitrate": int(self.info.get("bit_rate", 0) or 0),
            "audioSampleRate": int(self.info.get("audio_sample_rate", 0) or 0),
            "audioChannels": int(self.info.get("audio_channels", 0) or 0),
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


JOBS = JobManager(runner=run_prepare_review)
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


def _translation_mode(value: Any = None) -> tuple[str, bool]:
    mode_id = str(value or ("srt" if runtime_config.settings.get("aisendsrt", True) else "line"))
    mode = TRANSLATION_MODES.get(mode_id)
    if mode is None:
        raise ValueError(f"Unknown translation mode: {mode_id}")
    return mode_id, bool(mode["aisendsrt"])


def ensure_asr_configured(recogn_type: int, settings_store: Any) -> None:
    provider = ASR_BY_TYPE[recogn_type]
    settings_key = provider.get("settingsKey")
    if settings_key and not settings_store.get(settings_key):
        raise ValueError(f"Configure {provider['label']} API settings before starting")


def ensure_translation_configured(translate_type: int, settings_store: Any) -> None:
    provider = TRANSLATION_BY_TYPE[translate_type]
    key_name = provider.get("keyKey")
    if key_name and not settings_store.get(key_name):
        raise ValueError(f"Configure {provider['label']} settings before starting")


def _save_asr_settings(provider: dict[str, Any], payload: dict[str, Any], settings_store: Any) -> dict[str, bool]:
    settings_key = provider.get("settingsKey")
    if not settings_key:
        raise ValueError("This ASR provider has no WebUI API settings")
    api_key = str(payload.get("apiKey") or "").strip()
    if not api_key and not settings_store.get(settings_key):
        raise ValueError("API key is required")
    if api_key:
        settings_store[settings_key] = api_key
        settings_store.save()
    return {"configured": True}


def _translation_models(provider: dict[str, Any], settings_store: Any) -> list[str]:
    model_key = provider.get("modelKey")
    if not model_key:
        return []
    models = [item.strip() for item in str(runtime_config.settings.get(model_key, "")).split(",") if item.strip()]
    current = str(settings_store.get(model_key, "")).strip()
    if current and current not in models:
        models.insert(0, current)
    return models


def _translation_snapshot(provider: dict[str, Any], settings_store: Any) -> dict[str, Any]:
    key_name = provider.get("keyKey")
    model_key = provider.get("modelKey")
    base_url_key = provider.get("baseUrlKey")
    return {
        "id": provider["id"],
        "label": provider["label"],
        "translateType": provider["translateType"],
        "requiresSettings": bool(key_name),
        "configured": not key_name or bool(settings_store.get(key_name)),
        "baseUrl": str(settings_store.get(base_url_key, provider.get("defaultBaseUrl", ""))) if base_url_key else "",
        "model": str(settings_store.get(model_key, "")) if model_key else "",
        "models": _translation_models(provider, settings_store),
    }


def _save_translation_settings(provider: dict[str, Any], payload: dict[str, Any], settings_store: Any) -> dict[str, Any]:
    key_name = provider["keyKey"]
    api_key = str(payload.get("apiKey") or "").strip()
    if not api_key and not settings_store.get(key_name):
        raise ValueError("API key is required")

    model_key = provider["modelKey"]
    model = str(payload.get("model") or settings_store.get(model_key, "")).strip()
    if not model:
        raise ValueError("Model is required")

    base_url_key = provider["baseUrlKey"]
    base_url = str(payload.get("baseUrl") or settings_store.get(base_url_key, provider["defaultBaseUrl"])).strip()
    if provider["id"] == "openai":
        base_url = process_openai_api(base_url)
    elif base_url:
        if not re.match(r"^https?://", base_url, flags=re.I):
            raise ValueError("Base URL must start with http:// or https://")
        base_url = base_url.rstrip("/")

    if api_key:
        settings_store[key_name] = api_key
    settings_store[model_key] = model
    settings_store[base_url_key] = base_url
    settings_store.save()
    return _translation_snapshot(provider, settings_store)


def test_translation_provider(translate_type: int, aisendsrt: bool | None = None) -> str:
    if translate_type == translator.GOOGLE_INDEX and translator._check_google() is not True:
        raise RuntimeError("Google Translate is not reachable")
    raw = "你好啊我的朋友"
    translated = translator.run(
        translate_type=translate_type,
        text_list=[{"text": raw, "line": 1, "time": "00:00:00,000 --> 00:00:05,000"}],
        target_code="en",
        source_code="zh-cn",
        is_test=True,
        aisendsrt=aisendsrt,
    )
    if not translated or not translated[0].get("text"):
        raise RuntimeError("The translation provider returned no text")
    return str(translated[0]["text"])


def test_asr_provider(recogn_type: int, model_name: str) -> str:
    provider = ASR_BY_TYPE.get(recogn_type)
    if provider is None or not provider.get("thirdParty"):
        raise ValueError("Connection testing is only available for third-party ASR providers")
    if model_name not in provider["models"]:
        raise ValueError(f"Model {model_name} is not supported by {provider['label']}")

    sample_audio = Path(ROOT_DIR) / "videotrans" / "styles" / "no-remove.wav"
    with TemporaryDirectory(prefix="asr-test-", dir=TEMP_DIR) as cache_folder:
        result = recognition.run(
            audio_file=sample_audio.as_posix(),
            cache_folder=cache_folder,
            recogn_type=recogn_type,
            model_name=model_name,
            detect_language="zh-cn",
            uuid=f"asr-test-{uuid.uuid4().hex}",
        )
    if not result or not result[0].get("text"):
        raise RuntimeError("The ASR provider returned no transcription")
    return str(result[0]["text"])


def build_task_params(input_path: Path, options: dict[str, Any]) -> dict[str, Any]:
    """Translate supported frontend fields into the existing task configuration."""
    file_info = format_video(input_path.resolve().as_posix())
    safe_stem = re.sub(r"[^\w.-]+", "-", file_info.basename, flags=re.UNICODE).strip("-")
    target_dir = OUTPUT_DIR / (safe_stem or file_info.uuid)
    cache_dir = Path(TEMP_DIR) / file_info.uuid

    recogn_type = _required_index(options.get("recognType"), len(recognition.RECOGN_NAME_LIST), "ASR engine")
    asr_provider = ASR_BY_TYPE.get(recogn_type)
    if asr_provider is None:
        raise ValueError(f"Unsupported ASR engine: {recogn_type}")
    model_name = str(options.get("modelName") or asr_provider["models"][0])
    if model_name not in asr_provider["models"]:
        raise ValueError(f"Model {model_name} is not supported by {asr_provider['label']}")
    translate_type = _required_index(options.get("translateType"), len(translator.TRANSLASTE_NAME_LIST), "translation engine")
    if translate_type not in TRANSLATION_BY_TYPE:
        raise ValueError(f"Unsupported translation engine: {translate_type}")
    _, aisendsrt = _translation_mode(options.get("translationMode"))
    tts_type = _required_index(
        options.get("ttsType", tts.DEFAULT_TTS), len(tts.TTS_NAME_LIST), "voice engine"
    )
    source_language = str(options.get("sourceLanguage") or "")
    target_language = str(options.get("targetLanguage") or "")
    if source_language not in translator.LANGNAME_DICT:
        raise ValueError(f"Unknown source language: {source_language or 'missing'}")
    if target_language not in translator.LANGNAME_DICT:
        raise ValueError(f"Unknown target language: {target_language or 'missing'}")
    timing_mode = str(options.get("timingMode") or "voice")
    timing_flags = TIMING_MODES.get(timing_mode)
    if timing_flags is None:
        raise ValueError(f"Unknown timing mode: {timing_mode}")
    # Prepare ends at the transcript-review checkpoint. Voice selection belongs
    # to the later Voice & Dubbing stage, so it must not activate TTS here.
    voice_role = "No"

    params = asdict(file_info)
    params.update({
        "name": input_path.resolve().as_posix(),
        "target_dir": target_dir.resolve().as_posix(),
        "cache_folder": cache_dir.resolve().as_posix(),
        "source_language_code": source_language,
        "target_language_code": target_language,
        "recogn_type": recogn_type,
        "model_name": model_name,
        "translate_type": translate_type,
        "aisendsrt": aisendsrt,
        "tts_type": tts_type,
        "voice_role": voice_role,
        "is_cuda": bool(options.get("useCuda", False)),
        "remove_noise": bool(options.get("removeNoise", False)),
        "enable_diariz": bool(options.get("speakerDiarization", False)),
        "nums_diariz": int(options.get("speakerCount", 0) or 0),
        "voice_rate": str(options.get("voiceRate") or "+0%"),
        "volume": "+0%",
        "pitch": "+0Hz",
        **timing_flags,
        # Do not prepare/render video output during the ASR-only Prepare stage.
        "video_autorate": False,
        "subtitle_type": 0,
        "only_out_dubbed_audio": True,
        "clear_cache": True,
        "embed_bgm": False,
    })
    return params


async def options_handler(request: web.Request) -> web.Response:
    languages = [{"code": code, "name": name} for code, name in translator.LANGNAME_DICT.items()]
    settings_store = request.app["settings_store"]
    asr_providers = []
    for provider in ASR_PROVIDERS:
        settings_key = provider.get("settingsKey")
        asr_providers.append({
            "id": provider["id"],
            "label": provider["label"],
            "recognType": provider["recognType"],
            "models": list(provider["models"]),
            "requiresSettings": bool(settings_key),
            "configured": bool(settings_key and settings_store.get(settings_key)),
            "testable": bool(provider.get("thirdParty")),
        })
    return web.json_response({
        "languages": languages,
        "asrProviders": asr_providers,
        "translationProviders": [
            _translation_snapshot(provider, settings_store)
            for provider in TRANSLATION_PROVIDERS
        ],
        "translationModes": [
            {"id": mode_id, "label": mode["label"], "description": mode["description"]}
            for mode_id, mode in TRANSLATION_MODES.items()
        ],
        "voices": list(enumerate(tts.TTS_NAME_LIST)),
        "defaults": {
            "sourceLanguage": "zh-cn",
            "targetLanguage": "vi",
            "recognType": recognition.Deepgram,
            "modelName": "nova-3",
            "timingMode": "voice",
            "translateType": translator.GOOGLE_INDEX,
            "translationMode": _translation_mode()[0],
            "ttsType": tts.DEFAULT_TTS,
        },
    })


async def asr_settings_handler(request: web.Request) -> web.Response:
    provider = ASR_BY_ID.get(request.match_info["provider_id"])
    if provider is None or not provider.get("settingsKey"):
        raise web.HTTPNotFound(text="This ASR provider has no WebUI API settings")
    try:
        payload = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(text="A JSON settings request is required") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="ASR settings must be a JSON object")
    try:
        snapshot = _save_asr_settings(provider, payload, request.app["settings_store"])
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    return web.json_response(snapshot)


async def test_asr_settings_handler(request: web.Request) -> web.Response:
    provider = ASR_BY_ID.get(request.match_info["provider_id"])
    if provider is None or not provider.get("thirdParty"):
        raise web.HTTPNotFound(text="This ASR provider does not use a third-party connection")
    try:
        payload = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(text="A JSON settings request is required") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="ASR settings must be a JSON object")

    model_name = str(payload.get("model") or "").strip()
    if model_name not in provider["models"]:
        raise web.HTTPBadRequest(text=f"Model {model_name or 'missing'} is not supported by {provider['label']}")
    try:
        if provider.get("settingsKey"):
            _save_asr_settings(provider, payload, request.app["settings_store"])
        result = await asyncio.to_thread(
            request.app["asr_tester"], provider["recognType"], model_name
        )
    except Exception as exc:
        runtime_config.logger.exception("ASR connection test failed", exc_info=True)
        raise web.HTTPBadRequest(text=f"Connection test failed: {get_msg_from_except(exc)}") from exc
    return web.json_response({
        "ok": True,
        "message": "Connection successful",
        "model": model_name,
        "result": result,
    })


async def translation_settings_handler(request: web.Request) -> web.Response:
    provider = TRANSLATION_BY_ID.get(request.match_info["provider_id"])
    if provider is None or not provider.get("keyKey"):
        raise web.HTTPNotFound(text="This translation provider has no WebUI settings")
    try:
        payload = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(text="A JSON settings request is required") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="Translation settings must be a JSON object")
    try:
        snapshot = _save_translation_settings(provider, payload, request.app["settings_store"])
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    return web.json_response(snapshot)


async def test_translation_settings_handler(request: web.Request) -> web.Response:
    provider = TRANSLATION_BY_ID.get(request.match_info["provider_id"])
    if provider is None:
        raise web.HTTPNotFound(text="Unsupported translation provider")
    try:
        payload = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(text="A JSON settings request is required") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="Translation settings must be a JSON object")
    try:
        _, aisendsrt = _translation_mode(payload.get("translationMode"))
        if provider.get("keyKey"):
            _save_translation_settings(provider, payload, request.app["settings_store"])
        result = await asyncio.to_thread(
            request.app["translation_tester"], provider["translateType"], aisendsrt
        )
    except Exception as exc:
        runtime_config.logger.exception("Translation connection test failed", exc_info=True)
        raise web.HTTPBadRequest(text=f"Connection test failed: {get_msg_from_except(exc)}") from exc
    return web.json_response({"ok": True, "message": "Connection successful", "result": result})


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
        ensure_asr_configured(params["recogn_type"], request.app["settings_store"])
        ensure_translation_configured(params["translate_type"], request.app["settings_store"])
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
    settings_store: Any = None,
    asr_tester: Callable[[int, str], str] = test_asr_provider,
    translation_tester: Callable[[int, bool | None], str] = test_translation_provider,
) -> web.Application:
    if not (FRONTEND_DIR / "index.html").is_file():
        raise RuntimeError(f"Frontend not found: {FRONTEND_DIR}")
    app = web.Application(client_max_size=20 * 1024 ** 3)
    app["job_manager"] = job_manager or JOBS
    app["media_store"] = MEDIA if upload_dir is None and media_probe is get_video_info else MediaStore(upload_dir or UPLOAD_DIR, media_probe)
    app["settings_store"] = app_params if settings_store is None else settings_store
    app["asr_tester"] = asr_tester
    app["translation_tester"] = translation_tester
    app.router.add_get("/", index_handler)
    app.router.add_get("/api/options", options_handler)
    app.router.add_get("/api/voices", voices_handler)
    app.router.add_post("/api/asr-settings/{provider_id}", asr_settings_handler)
    app.router.add_post("/api/asr-settings/{provider_id}/test", test_asr_settings_handler)
    app.router.add_post("/api/translation-settings/{provider_id}", translation_settings_handler)
    app.router.add_post("/api/translation-settings/{provider_id}/test", test_translation_settings_handler)
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
