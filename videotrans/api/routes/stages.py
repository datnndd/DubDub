# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from typing import Any
from aiohttp import web

from videotrans.configure import config as runtime_config
from videotrans.configure.excepts import get_msg_from_except
from videotrans.task.orchestrator import (
    CancellationToken,
    TaskRequest,
    TaskStatus,
    run_staged_translation,
)
from videotrans.util.segment_ops import split_segment
from videotrans.api.task_params import _translation_mode
from videotrans.api.ocr_helpers import NormalizedRoi, extract_ocr_segment_text


async def translate_handler(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(text="A JSON translation request is required") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="Translation payload must be a JSON object")

    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, (list, tuple)):
        raise web.HTTPBadRequest(text="segments list is required")

    source_lang = str(payload.get("sourceLanguage") or "zh-cn")
    target_lang = str(payload.get("targetLanguage") or "en")
    translate_type = int(payload.get("translateType") or 0)
    _, aisendsrt = _translation_mode(payload.get("translationMode"))

    segments = []
    for s in raw_segments:
        if isinstance(s, dict):
            text = str(s.get("sourceText") or s.get("text") or "").strip()
            if text:
                segments.append({
                    "line": s.get("line", len(segments) + 1),
                    "time": s.get("time", "00:00:00,000 --> 00:00:01,000"),
                    "text": text,
                })

    if not segments:
        return web.json_response({"ok": True, "segments": []})

    task_params = {
        "source_code": source_lang,
        "target_code": target_lang,
        "translate_type": translate_type,
        "aisendsrt": aisendsrt,
        "segments": segments,
    }
    runner = getattr(request.app.get("job_manager"), "_translation_runner", None) or run_staged_translation
    token = CancellationToken()
    result = await asyncio.to_thread(runner, TaskRequest(task_params), None, token)
    if result.status == TaskStatus.FAILED:
        err_msg = result.failure.message if result.failure else "Translation failed"
        raise web.HTTPBadRequest(text=err_msg)
    return web.json_response({"ok": True, "segments": list(result.segments)})


async def ocr_extract_handler(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(text="A JSON OCR request is required") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="OCR payload must be a JSON object")

    media_id = str(payload.get("mediaId") or "")
    media_store = request.app["media_store"]
    media = media_store.get(media_id)
    if media is None or not media.path.is_file():
        raise web.HTTPNotFound(text="Select and inspect a media file before OCR extraction")

    try:
        start_sec = float(payload.get("startSec", 0.0))
        end_sec = float(payload.get("endSec", 0.0))
    except (TypeError, ValueError):
        raise web.HTTPBadRequest(text="startSec and endSec must be numeric")

    if end_sec <= start_sec or start_sec < 0:
        raise web.HTTPBadRequest(text="endSec must be strictly greater than startSec >= 0")

    roi = payload.get("roi")
    if isinstance(roi, dict):
        try:
            rx = float(roi.get("x", 0))
            ry = float(roi.get("y", 0))
            rw = float(roi.get("width", roi.get("w", 0)))
            rh = float(roi.get("height", roi.get("h", 0)))
            roi = [rx, ry, rw, rh]
        except (TypeError, ValueError):
            raise web.HTTPBadRequest(text="roi elements must be numeric")
    elif not (isinstance(roi, (list, tuple)) and len(roi) == 4):
        raise web.HTTPBadRequest(text="roi must be a 4-element list [x, y, w, h] or a dict with x, y, width, height")

    try:
        rx, ry, rw, rh = [float(v) for v in roi]
    except (TypeError, ValueError):
        raise web.HTTPBadRequest(text="roi elements must be numeric")

    if rw <= 0 or rh <= 0 or rx < 0 or ry < 0 or rx + rw > 1.05 or ry + rh > 1.05:
        raise web.HTTPBadRequest(text="roi must be normalized (0..1) with positive width and height")

    normalized_roi = NormalizedRoi(rx, ry, rw, rh)
    language = payload.get("language")

    ocr_extractor = request.app.get("ocr_extractor") or extract_ocr_segment_text
    try:
        try:
            result = await asyncio.to_thread(
                ocr_extractor,
                media.path,
                start_sec,
                end_sec,
                normalized_roi,
                language=language,
            )
        except TypeError:
            try:
                result = await asyncio.to_thread(
                    ocr_extractor,
                    media.path,
                    start_sec,
                    end_sec,
                    normalized_roi,
                    language,
                )
            except TypeError:
                result = await asyncio.to_thread(
                    ocr_extractor,
                    media.path,
                    start_sec,
                    end_sec,
                    normalized_roi,
                )
    except Exception as exc:
        runtime_config.logger.exception("OCR extraction failed", exc_info=True)
        raise web.HTTPBadRequest(text=f"OCR extraction failed: {get_msg_from_except(exc)}") from exc

    return web.json_response(result)


async def split_segment_handler(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(text="A JSON split request is required") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="Payload must be a JSON object")

    segment = payload.get("segment")
    if not isinstance(segment, dict):
        raise web.HTTPBadRequest(text="segment object is required")

    try:
        split_time = float(payload.get("splitTime"))
    except (TypeError, ValueError):
        raise web.HTTPBadRequest(text="splitTime must be numeric")

    cursor_pos = payload.get("cursorPosition")
    if cursor_pos is not None:
        try:
            cursor_pos = int(cursor_pos)
        except (TypeError, ValueError):
            cursor_pos = None

    next_id = payload.get("nextId") or payload.get("next_id")

    try:
        seg1, seg2 = split_segment(segment, split_time, cursor_pos, next_id=next_id)
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc

    return web.json_response({"ok": True, "segments": [seg1, seg2]})


def register_routes(app: web.Application) -> None:
    app.router.add_post("/api/translate", translate_handler)
    app.router.add_post("/api/ocr/extract", ocr_extract_handler)
    app.router.add_post("/api/segments/split", split_segment_handler)
