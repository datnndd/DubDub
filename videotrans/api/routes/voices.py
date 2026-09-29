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

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.datastructures import UploadFile

from videotrans import tts
from videotrans.api.catalog import TTS_PROVIDER_ALIASES
from videotrans.core import voice_store
from videotrans.services.audio_normalizer import (
    normalize_reference_audio,
)
from videotrans.services.voice_preview import (
    synthesize_voice_preview,
    synthesize_unified_tts_preview,
)

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("videotrans.api.voices")
router = APIRouter()


class VoiceUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    instruct: Optional[str] = None
    ref_text: Optional[str] = None
    language: Optional[str] = None
    tuning_params: Optional[dict[str, Any]] = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class VoicePreviewRequest(BaseModel):
    text: Optional[str] = None
    language: Optional[str] = None
    force_refresh: Optional[bool] = False

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class UnifiedTTSPreviewRequest(BaseModel):
    text: Optional[str] = None
    voice: Optional[str] = None
    voice_id: Optional[str] = Field(None, alias="voiceId")
    provider: Optional[Any] = None
    ttsType: Optional[Any] = Field(None, alias="tts_type")
    language: Optional[str] = None
    speed: Optional[float] = None
    rate: Optional[str] = None
    pitch: Optional[str] = None
    segment_id: Optional[Any] = Field(None, alias="segmentId")
    force_refresh: Optional[bool] = Field(False, alias="forceRefresh")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


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


@router.get("/api/custom-voices")
async def list_custom_voices_handler(
    provider: Optional[str] = None,
    active: str = "true",
) -> JSONResponse:
    parsed_provider = _parse_provider(provider) if provider is not None else None
    active_only = active.strip().lower() not in {"false", "0", "no"}
    voices = voice_store.list_voices(provider=parsed_provider, active_only=active_only)
    return JSONResponse({"voices": voices})


@router.get("/api/custom-voices/{id}")
async def get_custom_voice_handler(id: str) -> JSONResponse:
    voice = voice_store.get_voice(id)
    if not voice:
        raise HTTPException(status_code=404, detail=f"Voice {id} not found")
    return JSONResponse(voice)


@router.post("/api/custom-voices", status_code=201)
async def create_custom_voice_handler(request: Request) -> JSONResponse:
    voice_store.init_voice_dirs()
    fields: dict[str, Any] = {}
    audio_file_obj: Optional[UploadFile] = None
    audio_bytes: Optional[bytes] = None
    audio_filename: str = ""

    content_type = (request.headers.get("content-type") or "").lower()

    if "multipart" in content_type:
        try:
            form = await request.form()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid multipart form: {exc}") from exc

        for key, val in form.items():
            if key in {"audio", "file"}:
                if hasattr(val, "filename") and val.filename:
                    audio_file_obj = val
                    audio_filename = Path(unquote(val.filename)).name
                elif isinstance(val, (bytes, bytearray)):
                    audio_bytes = bytes(val)
                    audio_filename = "sample.wav"
            else:
                fields[key] = str(val)
    elif "json" in content_type:
        try:
            fields = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc
    else:
        raise HTTPException(status_code=400, detail="Expected multipart/form-data or application/json")

    raw_name = fields.get("name", "")
    clean_name = " ".join(str(raw_name).split())
    if not clean_name:
        raise HTTPException(status_code=400, detail="Voice name is required")

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

    if audio_file_obj:
        ext = Path(audio_filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            while chunk := await audio_file_obj.read(4 * 1024 * 1024):
                tmp_file.write(chunk)

        try:
            dest_filename = f"{voice_id}.wav"
            dest_path = voice_store.VOICES_DIR / dest_filename
            normalize_reference_audio(tmp_path, dest_path, provider=provider)
            ref_audio_rel = dest_filename
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Failed to normalize audio", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Audio normalization failed: {exc}") from exc
        finally:
            tmp_path.unlink(missing_ok=True)
    elif audio_bytes:
        ext = Path(audio_filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(audio_bytes)

        try:
            dest_filename = f"{voice_id}.wav"
            dest_path = voice_store.VOICES_DIR / dest_filename
            normalize_reference_audio(tmp_path, dest_path, provider=provider)
            ref_audio_rel = dest_filename
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Failed to normalize audio", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Audio normalization failed: {exc}") from exc
        finally:
            tmp_path.unlink(missing_ok=True)
    elif provider != tts.ELEVENLABS_TTS or not external_voice_id:
        raise HTTPException(status_code=400, detail="Audio file is required for voice cloning")

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

    return JSONResponse(created, status_code=201)


@router.put("/api/custom-voices/{id}")
async def update_custom_voice_handler(
    id: str,
    payload: VoiceUpdateRequest,
    request: Request,
) -> JSONResponse:
    voice = voice_store.get_voice(id)
    if not voice:
        raise HTTPException(status_code=404, detail=f"Voice {id} not found")

    update_dict = payload.model_dump(exclude_unset=True)
    try:
        updated = voice_store.update_voice(id, **update_dict)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not updated:
        raise HTTPException(status_code=404, detail=f"Voice {id} not found")

    return JSONResponse(updated)


@router.delete("/api/custom-voices/{id}")
async def delete_custom_voice_handler(
    id: str,
    hard: str = Query("false"),
) -> JSONResponse:
    voice = voice_store.get_voice(id)
    if not voice:
        raise HTTPException(status_code=404, detail=f"Voice {id} not found")

    hard_delete = hard.strip().lower() in {"true", "1", "yes"}
    success = voice_store.delete_voice(id, hard=hard_delete)
    if not success:
        raise HTTPException(status_code=404, detail=f"Voice {id} not found")

    return JSONResponse({"ok": True, "id": id, "hard": hard_delete})


class BulkDeleteVoicesRequest(BaseModel):
    ids: list[str]
    hard: Optional[bool] = False

    model_config = ConfigDict(populate_by_name=True, extra="allow")


@router.post("/api/custom-voices/bulk-delete")
@router.delete("/api/custom-voices/bulk-delete")
@router.post("/api/voices/bulk-delete")
@router.delete("/api/voices/bulk-delete")
async def bulk_delete_custom_voices_handler(payload: BulkDeleteVoicesRequest) -> JSONResponse:
    raw_ids = payload.ids or []
    deleted_ids = voice_store.bulk_delete_voices(raw_ids, hard=bool(payload.hard))
    return JSONResponse({"ok": True, "deleted": deleted_ids, "count": len(deleted_ids)})



@router.get("/api/custom-voices/{id}/audio")
async def get_custom_voice_audio_handler(id: str) -> FileResponse:
    voice = voice_store.get_voice(id)
    if not voice or not voice.get("ref_audio_path"):
        raise HTTPException(status_code=404, detail="Reference audio not found")

    try:
        audio_path = voice_store.get_voice_audio_path(voice["ref_audio_path"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not audio_path.is_file():
        raise HTTPException(status_code=404, detail="Reference audio file missing from storage")

    return FileResponse(audio_path, media_type="audio/wav")


@router.post("/api/custom-voices/{id}/preview")
async def create_custom_voice_preview_handler(
    id: str,
    payload: Optional[VoicePreviewRequest] = None,
    request: Request = None,
) -> JSONResponse:
    voice = voice_store.get_voice(id)
    if not voice:
        raise HTTPException(status_code=404, detail=f"Voice {id} not found")

    text = payload.text if payload else None
    language = payload.language if payload else None
    force_refresh = bool(payload.force_refresh) if payload else False

    try:
        preview_path = await synthesize_voice_preview(
            id,
            text=text,
            language=language,
            force_refresh=force_refresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Preview generation failed", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Preview generation failed: {exc}") from exc

    preview_url = f"/api/custom-voices/{id}/preview/audio"
    return JSONResponse({
        "ok": True,
        "voice_id": id,
        "preview_url": preview_url,
        "preview_filename": preview_path.name,
    })


@router.get("/api/custom-voices/{id}/preview/audio")
async def get_custom_voice_preview_audio_handler(id: str) -> FileResponse:
    voice = voice_store.get_voice(id)
    if not voice:
        raise HTTPException(status_code=404, detail=f"Voice {id} not found")

    preview_filename = voice.get("preview_audio_path") or f"{id}_preview.wav"
    try:
        preview_path = voice_store.get_preview_audio_path(preview_filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not preview_path.is_file():
        raise HTTPException(status_code=404, detail="Preview audio not generated yet")

    return FileResponse(preview_path, media_type="audio/wav")


@router.post("/api/tts/preview")
async def create_tts_preview_handler(
    payload: Optional[UnifiedTTSPreviewRequest] = None,
    request: Request = None,
) -> JSONResponse:
    payload_obj = payload or UnifiedTTSPreviewRequest()
    voice = (payload_obj.voice or payload_obj.voice_id or "").strip()
    provider = _parse_provider(payload_obj.provider if payload_obj.provider is not None else payload_obj.ttsType)
    text = (payload_obj.text or "").strip()
    language = (payload_obj.language or "").strip()
    force_refresh = bool(payload_obj.force_refresh)

    try:
        preview_id, preview_path = await synthesize_unified_tts_preview(
            provider=provider,
            voice=voice,
            text=text,
            language=language,
            force_refresh=force_refresh,
            speed=payload_obj.speed,
            rate=payload_obj.rate,
            pitch=payload_obj.pitch,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unified TTS preview generation failed", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Preview generation failed: {exc}") from exc

    preview_url = f"/api/tts/preview/{preview_id}/audio"
    return JSONResponse({
        "ok": True,
        "id": preview_id,
        "preview_id": preview_id,
        "preview_url": preview_url,
        "audio_url": preview_url,
        "voice": voice,
        "provider": provider,
    })


@router.get("/api/tts/preview/{id}/audio")
async def get_tts_preview_audio_handler(id: str) -> FileResponse:
    clean_id = Path(unquote(id)).name
    candidates = [
        clean_id if clean_id.endswith(".wav") else f"{clean_id}.wav",
        clean_id,
        f"{clean_id}_preview.wav",
    ]
    cv = voice_store.get_voice(clean_id)
    if cv and cv.get("preview_audio_path"):
        candidates.insert(0, cv["preview_audio_path"])

    audio_path = None
    for cand in candidates:
        try:
            p = voice_store.get_preview_audio_path(cand)
            if p.is_file() and p.stat().st_size > 0:
                audio_path = p
                break
        except ValueError:
            continue

    if not audio_path and cv and cv.get("ref_audio_path"):
        try:
            p = voice_store.get_voice_audio_path(cv["ref_audio_path"])
            if p.is_file() and p.stat().st_size > 0:
                audio_path = p
        except ValueError:
            pass

    if not audio_path or not audio_path.is_file():
        raise HTTPException(status_code=404, detail=f"Preview audio not found for ID: {id}")

    return FileResponse(audio_path, media_type="audio/wav")


def register_routes(app) -> None:
    app.include_router(router)
