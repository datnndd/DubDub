# -*- coding: utf-8 -*-
"""RESTful routes for custom voice cloning, audio management, and audition preview."""
from __future__ import annotations

import json
import logging
from pathlib import Path
import tempfile
import uuid
from typing import Any, Optional
from urllib.parse import unquote

from aiohttp import web

from videotrans import tts
from videotrans.api.catalog import TTS_PROVIDER_ALIASES
from videotrans.configure.config import ROOT_DIR
from videotrans.core import voice_store
from videotrans.services.audio_normalizer import (
    normalize_reference_audio,
    MIN_REFERENCE_DURATION_SEC,
    MAX_REFERENCE_DURATION_SEC,
)
from videotrans.services.voice_preview import synthesize_voice_preview

logger = logging.getLogger("videotrans.api.voices")


def _parse_provider(raw: Any) -> int:
    """Parse provider integer or alias string, defaulting to VieNeu (2)."""
    if raw is None:
        return tts.DEFAULT_TTS
    s = str(raw).strip().lower()
    if s in TTS_PROVIDER_ALIASES:
        return TTS_PROVIDER_ALIASES[s]
    try:
        val = int(s)
        if 0 <= val < len(tts.TTS_NAME_LIST):
            return val
    except ValueError:
        pass
    return tts.DEFAULT_TTS


async def list_custom_voices_handler(request: web.Request) -> web.Response:
    """GET /api/custom-voices"""
    raw_provider = request.query.get("provider")
    provider = _parse_provider(raw_provider) if raw_provider is not None else None

    raw_active = request.query.get("active", "true").strip().lower()
    active_only = raw_active not in {"false", "0", "no"}

    voices = voice_store.list_voices(provider=provider, active_only=active_only)
    return web.json_response({"voices": voices})


async def get_custom_voice_handler(request: web.Request) -> web.Response:
    """GET /api/custom-voices/{id}"""
    voice_id = request.match_info["id"]
    voice = voice_store.get_voice(voice_id)
    if not voice:
        raise web.HTTPNotFound(text=f"Voice {voice_id} not found")
    return web.json_response(voice)


async def create_custom_voice_handler(request: web.Request) -> web.Response:
    """
    POST /api/custom-voices
    Accepts multipart/form-data or application/json.
    Normalizes audio to 16-bit mono PCM WAV and creates voice profile.
    """
    voice_store.init_voice_dirs()
    fields: dict[str, Any] = {}
    audio_bytes: Optional[bytes] = None
    audio_filename: str = ""

    content_type = (request.content_type or "").lower()

    if "multipart" in content_type:
        reader = await request.multipart()
        async for part in reader:
            if part.name in {"audio", "file"} and part.filename:
                audio_filename = Path(unquote(part.filename)).name
                chunks = []
                while chunk := await part.read_chunk():
                    chunks.append(chunk)
                audio_bytes = b"".join(chunks)
            else:
                text_val = await part.text()
                fields[part.name] = text_val
    elif "json" in content_type:
        try:
            fields = await request.json()
        except Exception as exc:
            raise web.HTTPBadRequest(text=f"Invalid JSON: {exc}")
    else:
        raise web.HTTPBadRequest(text="Expected multipart/form-data or application/json")

    # Name validation
    raw_name = fields.get("name", "")
    clean_name = " ".join(str(raw_name).split())
    if not clean_name:
        raise web.HTTPBadRequest(text="Voice name is required")

    provider = _parse_provider(fields.get("provider"))
    language = str(fields.get("language") or "Auto").strip()
    description = str(fields.get("description") or "").strip()
    kind = str(fields.get("kind") or "clone").strip()
    ref_text = str(fields.get("ref_text") or "").strip()
    instruct = str(fields.get("instruct") or "").strip()
    external_voice_id = str(fields.get("external_voice_id") or "").strip()

    raw_tuning = fields.get("tuning_params") or fields.get("tuning") or {}
    if isinstance(raw_tuning, str):
        try:
            tuning_params = json.loads(raw_tuning)
        except Exception:
            tuning_params = {}
    elif isinstance(raw_tuning, dict):
        tuning_params = raw_tuning
    else:
        tuning_params = {}

    voice_id = f"voice_{uuid.uuid4().hex[:8]}"
    ref_audio_rel = ""

    # Audio normalization pipeline
    if audio_bytes:
        ext = Path(audio_filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_path.write_bytes(audio_bytes)

        try:
            dest_filename = f"{voice_id}.wav"
            dest_path = voice_store.VOICES_DIR / dest_filename
            normalize_reference_audio(tmp_path, dest_path, provider=provider)
            ref_audio_rel = dest_filename
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc))
        except Exception as exc:
            logger.exception("Failed to normalize audio", exc_info=True)
            raise web.HTTPBadRequest(text=f"Audio normalization failed: {exc}")
        finally:
            tmp_path.unlink(missing_ok=True)
    elif provider != tts.ELEVENLABS_TTS or not external_voice_id:
        raise web.HTTPBadRequest(text="Audio file is required for voice cloning")

    created = voice_store.create_voice(
        name=clean_name,
        provider=provider,
        voice_id=voice_id,
        description=description,
        kind=kind,
        language=language,
        ref_audio_path=ref_audio_rel,
        ref_text=ref_text,
        instruct=instruct,
        external_voice_id=external_voice_id,
        tuning_params=tuning_params,
    )

    return web.json_response(created, status=201)


async def update_custom_voice_handler(request: web.Request) -> web.Response:
    """PUT /api/custom-voices/{id}"""
    voice_id = request.match_info["id"]
    voice = voice_store.get_voice(voice_id)
    if not voice:
        raise web.HTTPNotFound(text=f"Voice {voice_id} not found")

    try:
        payload = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(text=f"Invalid JSON: {exc}")

    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="Request body must be a JSON object")

    try:
        updated = voice_store.update_voice(voice_id, **payload)
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc))

    if not updated:
        raise web.HTTPNotFound(text=f"Voice {voice_id} not found")

    return web.json_response(updated)


async def delete_custom_voice_handler(request: web.Request) -> web.Response:
    """DELETE /api/custom-voices/{id}"""
    voice_id = request.match_info["id"]
    voice = voice_store.get_voice(voice_id)
    if not voice:
        raise web.HTTPNotFound(text=f"Voice {voice_id} not found")

    hard_delete = request.query.get("hard", "").strip().lower() in {"true", "1", "yes"}
    success = voice_store.delete_voice(voice_id, hard=hard_delete)
    if not success:
        raise web.HTTPNotFound(text=f"Voice {voice_id} not found")

    return web.json_response({"ok": True, "id": voice_id, "hard": hard_delete})


async def get_custom_voice_audio_handler(request: web.Request) -> web.Response:
    """GET /api/custom-voices/{id}/audio"""
    voice_id = request.match_info["id"]
    voice = voice_store.get_voice(voice_id)
    if not voice or not voice.get("ref_audio_path"):
        raise web.HTTPNotFound(text="Reference audio not found")

    try:
        audio_path = voice_store.get_voice_audio_path(voice["ref_audio_path"])
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc))

    if not audio_path.is_file():
        raise web.HTTPNotFound(text="Reference audio file missing from storage")

    return web.FileResponse(audio_path, headers={"Content-Type": "audio/wav"})


async def create_custom_voice_preview_handler(request: web.Request) -> web.Response:
    """POST /api/custom-voices/{id}/preview"""
    voice_id = request.match_info["id"]
    voice = voice_store.get_voice(voice_id)
    if not voice:
        raise web.HTTPNotFound(text=f"Voice {voice_id} not found")

    text = None
    language = None
    force_refresh = False

    if request.can_read_body:
        try:
            payload = await request.json()
            if isinstance(payload, dict):
                text = payload.get("text")
                language = payload.get("language")
                force_refresh = bool(payload.get("force_refresh", False))
        except Exception:
            pass

    try:
        preview_path = await synthesize_voice_preview(
            voice_id,
            text=text,
            language=language,
            force_refresh=force_refresh,
        )
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc))
    except Exception as exc:
        logger.exception("Preview generation failed", exc_info=True)
        raise web.HTTPInternalServerError(text=f"Preview generation failed: {exc}")

    preview_url = f"/api/custom-voices/{voice_id}/preview/audio"
    return web.json_response({
        "ok": True,
        "voice_id": voice_id,
        "preview_url": preview_url,
        "preview_filename": preview_path.name,
    })


async def get_custom_voice_preview_audio_handler(request: web.Request) -> web.Response:
    """GET /api/custom-voices/{id}/preview/audio"""
    voice_id = request.match_info["id"]
    voice = voice_store.get_voice(voice_id)
    if not voice:
        raise web.HTTPNotFound(text=f"Voice {voice_id} not found")

    preview_filename = voice.get("preview_audio_path") or f"{voice_id}_preview.wav"
    try:
        preview_path = voice_store.get_preview_audio_path(preview_filename)
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc))

    if not preview_path.is_file():
        raise web.HTTPNotFound(text="Preview audio not generated yet")

    return web.FileResponse(preview_path, headers={"Content-Type": "audio/wav"})


def register_routes(app: web.Application) -> None:
    app.router.add_get("/api/custom-voices", list_custom_voices_handler)
    app.router.add_post("/api/custom-voices", create_custom_voice_handler)
    app.router.add_get("/api/custom-voices/{id}", get_custom_voice_handler)
    app.router.add_put("/api/custom-voices/{id}", update_custom_voice_handler)
    app.router.add_delete("/api/custom-voices/{id}", delete_custom_voice_handler)
    app.router.add_get("/api/custom-voices/{id}/audio", get_custom_voice_audio_handler)
    app.router.add_post("/api/custom-voices/{id}/preview", create_custom_voice_preview_handler)
    app.router.add_get("/api/custom-voices/{id}/preview/audio", get_custom_voice_preview_audio_handler)
